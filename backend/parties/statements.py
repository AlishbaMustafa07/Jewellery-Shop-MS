"""Running-balance account statements for customers and suppliers."""
from decimal import Decimal

ZERO = Decimal("0")


def _finish(rows, opening_base, date_from, date_to):
    rows.sort(key=lambda r: (r["date"], r["_order"]))
    balance = opening_base
    opening = opening_base
    out = []
    for r in rows:
        balance += r["debit"] - r["credit"]
        if date_from and r["date"] < date_from:
            opening = balance
            continue
        if date_to and r["date"] > date_to:
            continue
        r = {k: v for k, v in r.items() if k != "_order"}
        r["balance"] = balance
        out.append(r)
    closing = out[-1]["balance"] if out else opening
    return {
        "opening_balance": opening,
        "rows": out,
        "total_debit": sum((r["debit"] for r in out), ZERO),
        "total_credit": sum((r["credit"] for r in out), ZERO),
        "closing_balance": closing,
    }


def customer_statement(customer, date_from=None, date_to=None):
    from sales.models import Invoice, OldGoldIntake, Payment

    rows = []
    invoices = Invoice.objects.filter(customer=customer).exclude(status=Invoice.Status.VOIDED)
    for inv in invoices:
        rows.append(dict(date=inv.date, _order=inv.created_at, type="Sale", ref=inv.number,
                         description=f"Invoice {inv.number}" + (f" (Book {inv.legacy_book}/{inv.legacy_page})"
                                                                if inv.legacy_book else ""),
                         debit=inv.net_amount, credit=ZERO))
    for og in OldGoldIntake.objects.filter(invoice__in=invoices).select_related("invoice"):
        rows.append(dict(date=og.invoice.date, _order=og.created_at, type="Old gold", ref=og.invoice.number,
                         description=f"Old gold {og.weight} g @ {og.ratti_kaat} ratti", debit=ZERO, credit=og.value))
    payments = (Payment.objects.filter(customer=customer, is_voided=False)
                .exclude(method=Payment.Method.ADVANCE).select_related("invoice"))
    for p in payments:
        label = "Advance" if p.kind == Payment.Kind.ADVANCE else "Payment"
        rows.append(dict(date=p.date, _order=p.created_at, type=label, ref=p.invoice.number if p.invoice else "",
                         description=f"{label} ({p.get_method_display()})" + (f" {p.reference}" if p.reference else ""),
                         debit=ZERO, credit=p.amount))
    return _finish(rows, customer.opening_balance, date_from, date_to)


def supplier_statement(supplier, date_from=None, date_to=None):
    from .models import SupplierTransaction

    rows = []
    for t in supplier.transactions.filter(is_voided=False).select_related("stock_item"):
        increase = t.type in SupplierTransaction.CREDIT_TYPES
        rows.append(dict(
            date=t.date, _order=t.created_at, type=t.get_type_display(),
            ref=t.stock_item.code if t.stock_item else "",
            description=t.notes or t.get_type_display(),
            debit=t.amount if increase else ZERO, credit=ZERO if increase else t.amount,
            gold_pasa=t.gold_pasa,
        ))
    return _finish(rows, supplier.opening_balance, date_from, date_to)


STATEMENT_COLUMNS = [
    ("date", "Date"), ("type", "Type"), ("ref", "Ref"), ("description", "Description"),
    ("debit", "Debit"), ("credit", "Credit"), ("balance", "Balance"),
]
