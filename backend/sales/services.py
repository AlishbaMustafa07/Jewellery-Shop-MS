"""Sale flow: preview, create, pay, void. Everything runs in one DB transaction."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from cashbook import services as cashbook
from core import audit
from core import calculations as calc
from core.exceptions import BusinessRuleError
from core.models import AuditLog, GoldRate, Sequence, ShopSettings
from parties.models import Customer
from stock.models import StockItem

from .models import Invoice, OldGoldIntake, Payment, SaleLine

ZERO = Decimal("0")


def default_cash_account(method):
    accounts = ShopSettings.load().cash_accounts
    wanted = "shop_cash" if method == Payment.Method.CASH else "bank"
    if wanted in accounts:
        return wanted
    return accounts[0]


def resolve_sale_rate(date, rate=None):
    if rate:
        return calc.D(rate)
    gr = GoldRate.for_date(date)
    if not gr:
        raise BusinessRuleError("No gold rate is set. Enter today's rate before making a sale.")
    return gr.sell_rate_per_tola


def resolve_buy_rate(date, rate=None):
    if rate:
        return calc.D(rate)
    gr = GoldRate.for_date(date)
    if not gr:
        raise BusinessRuleError("No gold rate is set. Enter today's rate first.")
    return gr.buy_rate_per_tola


def _get_item(line):
    item = line.get("stock_item")
    if item is None and line.get("stock_code"):
        item = StockItem.objects.filter(code=line["stock_code"].strip().upper()).first()
        if item is None:
            raise BusinessRuleError(f"No stock item with code {line['stock_code']}.")
    return item


def compute_line(line, sale_rate, basis):
    """Price one sale line. Returns a dict of SaleLine field values."""
    item = _get_item(line)
    making_mode = line.get("making_mode") or calc.MakingMode.FIXED
    making_rate = calc.D(line.get("making_rate"))
    stone_value = calc.q_money(line.get("stone_value"))

    if item is not None:
        weight = item.gold_weight
        ratti = item.ratti_kaat
        pasa_value = item.pasa
        description = line.get("description") or f"{item.code} {item.category} {item.name}".strip()
        if item.metal == StockItem.Metal.GOLD:
            # Full-precision pasa, exactly like purchase costing (stored pasa is rounded to 4 dp).
            exact = calc.pasa_exact(weight, ratti) if basis == "pasa" else weight
            gold_value = calc.value_of_pasa(exact, sale_rate)
        else:
            # Silver/palladium are priced by hand (gold rate does not apply).
            gold_value = calc.q_money(line.get("gold_value"))
        purchase_cost = item.total_cost
    else:
        description = (line.get("description") or "").strip()
        if not description:
            raise BusinessRuleError("Misc (non-stock) lines need a description.")
        weight = calc.q_weight(line.get("weight"))
        ratti = line.get("ratti_kaat")
        pasa_value = calc.pasa(weight, ratti) if ratti else calc.q_pasa(line.get("pasa"))
        if line.get("gold_value") not in (None, ""):
            gold_value = calc.q_money(line.get("gold_value"))
        elif pasa_value:
            exact = calc.pasa_exact(weight, ratti) if ratti else pasa_value
            gold_value = calc.value_of_pasa(exact if basis == "pasa" else weight, sale_rate)
        else:
            gold_value = ZERO
        purchase_cost = calc.q_money(line.get("purchase_cost"))

    if line.get("making_charges") not in (None, ""):
        making = calc.q_money(line.get("making_charges"))
    else:
        making = calc.making_charges(making_mode, making_rate, weight, gold_value)

    total = calc.q_money(gold_value + making + stone_value)
    return {
        "stock_item": item,
        "description": description[:200],
        "weight": weight,
        "ratti_kaat": ratti,
        "pasa": pasa_value,
        "gold_value": gold_value,
        "making_mode": making_mode,
        "making_rate": making_rate,
        "making_charges": making,
        "stone_value": stone_value,
        "line_total": total,
        "purchase_cost": purchase_cost,
        "profit": total - purchase_cost,
    }


def compute_old_gold(og, date):
    weight = calc.q_weight(og.get("weight"))
    ratti = calc.D(og.get("ratti_kaat"))
    if weight <= 0 or not (0 < ratti <= 96):
        raise BusinessRuleError("Old gold needs a weight above zero and ratti kaat between 0 and 96.")
    rate = resolve_buy_rate(date, og.get("rate"))
    deduction = calc.q_money(og.get("deduction"))
    value = calc.gold_price(weight, ratti, rate) - deduction
    return {
        "description": (og.get("description") or "")[:200],
        "weight": weight,
        "ratti_kaat": ratti,
        "pasa": calc.pasa(weight, ratti),
        "rate": rate,
        "deduction": deduction,
        "value": max(value, ZERO),
    }


def preview(data):
    """Price a sale without saving anything (used by the counter screen)."""
    date = data.get("date") or timezone.localdate()
    shop = ShopSettings.load()
    sale_rate = resolve_sale_rate(date, data.get("sale_rate"))
    lines = [compute_line(line, sale_rate, shop.sale_gold_basis) for line in data.get("lines", [])]
    old_gold = [compute_old_gold(og, date) for og in data.get("old_gold", [])]
    subtotal = sum((l["line_total"] for l in lines), ZERO)
    discount = calc.q_money(data.get("discount"))
    net = subtotal - discount
    og_credit = sum((o["value"] for o in old_gold), ZERO)
    payments = sum((calc.D(p.get("amount")) for p in data.get("payments", [])), ZERO)
    return {
        "date": date,
        "sale_rate": sale_rate,
        "lines": lines,
        "old_gold": old_gold,
        "subtotal": subtotal,
        "discount": discount,
        "net_amount": net,
        "old_gold_credit": og_credit,
        "payments_total": payments,
        "balance": net - og_credit - payments,
        "profit": sum((l["profit"] for l in lines), ZERO) - discount,
    }


def _check_discount(user, discount):
    limit = user.effective_discount_limit()
    if limit is not None and discount > limit:
        raise BusinessRuleError(
            f"Discount Rs {discount:,.0f} is above your limit of Rs {limit:,.0f}. Ask a manager or the owner."
        )


def _record_payment(*, invoice, customer, kind, method, amount, date, cash_account, reference, notes, user,
                    party):
    amount = calc.q_money(amount)
    if amount <= 0:
        raise BusinessRuleError("Payment amount must be greater than zero.")
    cash_account = cash_account or default_cash_account(method)
    payment = Payment.objects.create(
        invoice=invoice, customer=customer, kind=kind, method=method, amount=amount, date=date,
        cash_account=cash_account, reference=reference or "", notes=notes or "", created_by=user,
    )
    if method != Payment.Method.ADVANCE:
        key = {Payment.Kind.SALE: "sale", Payment.Kind.ADVANCE: "advance",
               Payment.Kind.RECEIVABLE: "customer_payment"}[kind]
        entry = cashbook.post_entry(
            key=key, date=date, amount=amount, user=user,
            source_type={"sale": "sale", "advance": "advance", "customer_payment": "customer_payment"}[key],
            source_id=payment.id, party=party, detail=method.title() + (f" {reference}" if reference else ""),
            cash_account=cash_account, notes=f"Invoice {invoice.number}" if invoice else notes or "",
        )
        payment.cash_book_entry = entry
        payment.save(update_fields=["cash_book_entry"])
    audit.log_create(user, payment)
    return payment


def _next_invoice_number():
    shop = ShopSettings.load()
    floor = 0
    last = Invoice.objects.filter(number__startswith=f"{shop.invoice_prefix}-").order_by("-number").first()
    if last:
        try:
            floor = int(last.number.split("-")[-1])
        except ValueError:
            floor = 0
    return f"{shop.invoice_prefix}-{Sequence.next_value('invoice', floor=floor):06d}"


@transaction.atomic
def create_invoice(data, user):
    today = timezone.localdate()
    date = data.get("date") or today
    if date != today and user.role not in ("owner", "manager"):
        raise BusinessRuleError("Only the owner or a manager can enter a sale for another date.")
    if date > today:
        raise BusinessRuleError("Sale date cannot be in the future.")
    if not data.get("lines"):
        raise BusinessRuleError("Add at least one item to the sale.")

    customer = data.get("customer")
    if customer is None and data.get("new_customer"):
        nc = data["new_customer"]
        customer = Customer.objects.create(name=nc["name"], phone=nc.get("phone", ""), address=nc.get("address", ""))
        audit.log_create(user, customer, note="Created at counter")

    # Lock the stock rows being sold so two counters cannot sell the same piece.
    item_ids = [l["stock_item"].pk for l in data["lines"] if l.get("stock_item")]
    codes = [l["stock_code"].strip().upper() for l in data["lines"] if not l.get("stock_item") and l.get("stock_code")]
    locked = {i.pk: i for i in StockItem.objects.select_for_update().filter(pk__in=item_ids)}
    locked.update({i.pk: i for i in StockItem.objects.select_for_update().filter(code__in=codes)})
    seen = set()
    for line in data["lines"]:
        item = _get_item(line)
        if item is None:
            continue
        item = locked[item.pk]
        line["stock_item"] = item
        if item.pk in seen:
            raise BusinessRuleError(f"Item {item.code} is on the invoice twice.")
        seen.add(item.pk)
        if item.status != StockItem.Status.IN_STOCK:
            raise BusinessRuleError(f"Item {item.code} is not in stock (status: {item.get_status_display()}).")

    p = preview({**data, "date": date})
    _check_discount(user, p["discount"])
    if p["net_amount"] < 0:
        raise BusinessRuleError("Discount cannot exceed the invoice subtotal.")

    payments = data.get("payments", [])
    advance_used = sum((calc.D(x["amount"]) for x in payments if x["method"] == Payment.Method.ADVANCE), ZERO)
    if advance_used:
        if not customer:
            raise BusinessRuleError("Select the customer whose advance is being adjusted.")
        available = customer.advance_credit()
        if advance_used > available:
            raise BusinessRuleError(f"Customer only has Rs {available:,.0f} of advance available.")
    if p["balance"] < 0:
        raise BusinessRuleError(
            f"Payments and old gold exceed the net amount by Rs {-p['balance']:,.0f}. Give change instead of recording it."
        )
    if not customer and p["balance"] > 0:
        raise BusinessRuleError("Walk-in sales must be paid in full. Select or add a customer to leave a balance.")

    invoice = Invoice.objects.create(
        number=_next_invoice_number(), date=date, customer=customer,
        customer_name=data.get("customer_name", "") if not customer else "",
        customer_phone=data.get("customer_phone", "") if not customer else "",
        legacy_book=data.get("legacy_book", ""), legacy_page=data.get("legacy_page", ""),
        sale_rate=p["sale_rate"], subtotal=p["subtotal"], discount=p["discount"], net_amount=p["net_amount"],
        old_gold_credit=p["old_gold_credit"], salesperson=user, notes=data.get("notes", ""),
    )
    for values in p["lines"]:
        SaleLine.objects.create(invoice=invoice, **values)
        item = values["stock_item"]
        if item is not None:
            item.status = StockItem.Status.SOLD
            item.sold_date = date
            item.updated_by = user
            item.save()
    for og in p["old_gold"]:
        OldGoldIntake.objects.create(invoice=invoice, **og)

    party = invoice.display_customer
    for pay in payments:
        _record_payment(
            invoice=invoice, customer=customer, kind=Payment.Kind.SALE, method=pay["method"], amount=pay["amount"],
            date=date, cash_account=pay.get("cash_account"), reference=pay.get("reference"), notes="", user=user,
            party=party,
        )
    invoice.refresh_totals()
    if customer:
        customer.recompute_balance()
    audit.log_create(user, invoice, note=f"Sale of {len(p['lines'])} line(s), net {p['net_amount']}")
    return invoice


@transaction.atomic
def add_payment(invoice, data, user):
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.VOIDED:
        raise BusinessRuleError("Cannot take payment on a voided invoice.")
    amount = calc.q_money(data["amount"])
    if amount > invoice.balance:
        raise BusinessRuleError(f"Payment exceeds the outstanding balance of Rs {invoice.balance:,.0f}.")
    if data["method"] == Payment.Method.ADVANCE:
        if not invoice.customer or amount > invoice.customer.advance_credit():
            raise BusinessRuleError("Not enough advance available for this customer.")
    payment = _record_payment(
        invoice=invoice, customer=invoice.customer, kind=Payment.Kind.RECEIVABLE, method=data["method"],
        amount=amount, date=data.get("date") or timezone.localdate(), cash_account=data.get("cash_account"),
        reference=data.get("reference"), notes=data.get("notes"), user=user, party=invoice.display_customer,
    )
    invoice.refresh_totals()
    if invoice.customer:
        invoice.customer.recompute_balance()
    return payment


@transaction.atomic
def receive_customer_payment(customer, data, user):
    """Payment against a customer's outstanding balance, allocated to the oldest open invoices first."""
    remaining = calc.q_money(data["amount"])
    if remaining <= 0:
        raise BusinessRuleError("Amount must be greater than zero.")
    if data["method"] == Payment.Method.ADVANCE:
        raise BusinessRuleError("Use a real payment method here.")
    date = data.get("date") or timezone.localdate()
    created = []
    open_invoices = (Invoice.objects.select_for_update().filter(customer=customer, balance__gt=0)
                     .exclude(status=Invoice.Status.VOIDED).order_by("date", "number"))
    for inv in open_invoices:
        if remaining <= 0:
            break
        part = min(remaining, inv.balance)
        created.append(_record_payment(
            invoice=inv, customer=customer, kind=Payment.Kind.RECEIVABLE, method=data["method"], amount=part,
            date=date, cash_account=data.get("cash_account"), reference=data.get("reference"),
            notes=data.get("notes"), user=user, party=customer.name,
        ))
        inv.refresh_totals()
        remaining -= part
    if remaining > 0:
        # Covers opening (pre-system) balances; anything beyond that leaves the customer in credit.
        created.append(_record_payment(
            invoice=None, customer=customer, kind=Payment.Kind.RECEIVABLE, method=data["method"], amount=remaining,
            date=date, cash_account=data.get("cash_account"), reference=data.get("reference"),
            notes=data.get("notes") or "Against opening balance", user=user, party=customer.name,
        ))
    customer.recompute_balance()
    return created


@transaction.atomic
def create_advance(customer, data, user):
    if data["method"] == Payment.Method.ADVANCE:
        raise BusinessRuleError("Choose cash, bank or card for an advance.")
    payment = _record_payment(
        invoice=None, customer=customer, kind=Payment.Kind.ADVANCE, method=data["method"], amount=data["amount"],
        date=data.get("date") or timezone.localdate(), cash_account=data.get("cash_account"),
        reference=data.get("reference"), notes=data.get("notes"), user=user, party=customer.name,
    )
    customer.recompute_balance()
    return payment


@transaction.atomic
def void_invoice(invoice, user, reason):
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.VOIDED:
        raise BusinessRuleError("Invoice is already voided.")
    if not reason or not reason.strip():
        raise BusinessRuleError("A reason is required to void an invoice.")
    if invoice.old_gold.exclude(status=OldGoldIntake.Status.PENDING).exists():
        raise BusinessRuleError("Old gold from this invoice has already gone to refine; remove it from the lot first.")
    old = audit.snapshot(invoice)
    for line in invoice.lines.select_related("stock_item"):
        item = line.stock_item
        if item and item.status == StockItem.Status.SOLD:
            item.status = StockItem.Status.IN_STOCK
            item.sold_date = None
            item.updated_by = user
            item.save()
    for payment in invoice.payments.filter(is_voided=False):
        payment.is_voided = True
        payment.save(update_fields=["is_voided", "updated_at"])
        if payment.cash_book_entry:
            cashbook.void_or_reverse(payment.cash_book_entry, user, f"Invoice {invoice.number} voided: {reason}")
    invoice.status = Invoice.Status.VOIDED
    invoice.voided_at = timezone.now()
    invoice.voided_by = user
    invoice.void_reason = reason.strip()[:300]
    invoice.save()
    invoice.refresh_totals()
    if invoice.customer:
        invoice.customer.recompute_balance()
    audit.log(user, AuditLog.Action.VOID, invoice, audit.diff(old, audit.snapshot(invoice)), note=reason)
    return invoice


@transaction.atomic
def void_payment(payment, user, reason):
    if payment.is_voided:
        raise BusinessRuleError("Payment is already voided.")
    if payment.kind == Payment.Kind.ADVANCE and payment.customer and payment.customer.advance_credit() < payment.amount:
        raise BusinessRuleError("This advance has already been used against an invoice.")
    payment.is_voided = True
    payment.save(update_fields=["is_voided", "updated_at"])
    if payment.cash_book_entry:
        cashbook.void_or_reverse(payment.cash_book_entry, user, reason)
    if payment.invoice:
        payment.invoice.refresh_totals()
    if payment.customer:
        payment.customer.recompute_balance()
    audit.log(user, AuditLog.Action.VOID, payment, note=reason)
    return payment
