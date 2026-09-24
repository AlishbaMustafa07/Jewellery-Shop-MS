"""Report calculations. Every function takes plain dates and returns plain dicts."""
import datetime
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone

from cashbook import services as cashbook
from cashbook.models import CashBookEntry
from core import calculations as calc
from core.models import GoldRate, ShopSettings
from parties.models import Customer, Supplier
from sales.models import Invoice, OldGoldIntake, SaleLine
from stock.models import StockItem

ZERO = Decimal("0")

# Report groups that are NOT operating expenses/income of the shop.
NON_OPERATING_GROUPS = {"shop_purchase", "investors", "home", "zakat", "adjustments", "sales"}
DRAWINGS_GROUPS = {"home", "zakat"}


def _z(v):
    return v if v is not None else ZERO


def latest_rate():
    return GoldRate.objects.order_by("-date").first()


def _live_invoices(date_from=None, date_to=None):
    qs = Invoice.objects.exclude(status=Invoice.Status.VOIDED)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _entries(date_from=None, date_to=None):
    qs = CashBookEntry.objects.filter(is_voided=False)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def profit_loss(date_from, date_to):
    invoices = _live_invoices(date_from, date_to)
    lines = SaleLine.objects.filter(invoice__in=invoices)
    agg = invoices.aggregate(net=Sum("net_amount"), discount=Sum("discount"), subtotal=Sum("subtotal"),
                             count=Count("id"))
    line_agg = lines.aggregate(cost=Sum("purchase_cost"), profit=Sum("profit"))

    by_category = []
    for row in (lines.values("stock_item__category")
                .annotate(items=Count("id"), weight=Sum("weight"), pasa=Sum("pasa"), sales=Sum("line_total"),
                          cost=Sum("purchase_cost"), profit=Sum("profit"))
                .order_by("-sales")):
        by_category.append({
            "category": row["stock_item__category"] or "Misc (non-stock)",
            "items": row["items"], "weight": _z(row["weight"]), "pasa": _z(row["pasa"]),
            "sales": _z(row["sales"]), "cost": _z(row["cost"]), "profit": _z(row["profit"]),
        })

    entries = _entries(date_from, date_to)
    expenses, other_income, drawings = [], [], []
    for row in (entries.values("type", "hoa__name", "hoa__report_group")
                .annotate(total=Sum("amount")).order_by("hoa__name")):
        group = row["hoa__report_group"] or ""
        item = {"head": row["hoa__name"], "group": group, "total": row["total"]}
        if row["type"] == "E":
            if group in DRAWINGS_GROUPS:
                drawings.append(item)
            elif group not in NON_OPERATING_GROUPS:
                expenses.append(item)
        elif group not in NON_OPERATING_GROUPS:
            other_income.append(item)

    gross_profit = _z(line_agg["profit"]) - _z(agg["discount"])
    total_expenses = sum((e["total"] for e in expenses), ZERO)
    total_other = sum((e["total"] for e in other_income), ZERO)
    net_profit = gross_profit + total_other - total_expenses
    return {
        "date_from": date_from, "date_to": date_to,
        "invoice_count": agg["count"],
        "sales_subtotal": _z(agg["subtotal"]), "discount": _z(agg["discount"]), "net_sales": _z(agg["net"]),
        "cost_of_goods_sold": _z(line_agg["cost"]),
        "gross_profit": gross_profit,
        "by_category": by_category,
        "other_income": other_income, "total_other_income": total_other,
        "expenses": expenses, "total_expenses": total_expenses,
        "net_profit": net_profit,
        "drawings": drawings, "total_drawings": sum((d["total"] for d in drawings), ZERO),
        "note": "Home and zakat are shown as drawings below net profit. Supplier payments are stock purchases, "
                "not expenses (cost is recognised when an item is sold).",
    }


def stock_valuation(slow_days=None):
    slow_days = slow_days or settings.SLOW_MOVING_DAYS
    rate = latest_rate()
    sell = rate.sell_rate_per_tola if rate else None
    in_stock = StockItem.objects.filter(status=StockItem.Status.IN_STOCK)
    groups = []
    for row in (in_stock.values("metal", "category")
                .annotate(items=Count("id"), pieces=Sum("pieces"), gross=Sum("gross_weight"), gold=Sum("gold_weight"),
                          pasa=Sum("pasa"), cost=Sum("total_cost"), extra=Sum("extra_costs"))
                .order_by("metal", "category")):
        at_rate = None
        if sell and row["metal"] == StockItem.Metal.GOLD:
            at_rate = calc.value_of_pasa(row["pasa"], sell) + _z(row["extra"])
        groups.append({
            "metal": row["metal"], "category": row["category"], "items": row["items"], "pieces": row["pieces"],
            "gross_weight": row["gross"], "gold_weight": row["gold"], "pasa": row["pasa"],
            "cost": row["cost"], "value_at_today": at_rate,
            "unrealised_gain": (at_rate - row["cost"]) if at_rate is not None else None,
        })
    cutoff = timezone.localdate() - datetime.timedelta(days=slow_days)
    slow = (in_stock.filter(Q(purchase_date__lt=cutoff) | Q(purchase_date__isnull=True, created_at__date__lt=cutoff))
            .order_by("purchase_date")
            .values("id", "code", "category", "metal", "gross_weight", "pasa", "total_cost", "purchase_date")[:500])
    totals = {
        "items": sum(g["items"] for g in groups), "pieces": sum(_z(g["pieces"]) for g in groups),
        "gross_weight": sum((_z(g["gross_weight"]) for g in groups), ZERO),
        "pasa": sum((_z(g["pasa"]) for g in groups), ZERO), "cost": sum((_z(g["cost"]) for g in groups), ZERO),
        "value_at_today": sum((g["value_at_today"] or ZERO for g in groups), ZERO) if sell else None,
    }
    return {"rate": sell, "rate_date": rate.date if rate else None, "groups": groups, "totals": totals,
            "slow_moving_days": slow_days, "slow_moving": list(slow)}


def sales_report(date_from, date_to, group_by="day"):
    invoices = _live_invoices(date_from, date_to)
    lines = SaleLine.objects.filter(invoice__in=invoices)
    if group_by in ("day", "month"):
        trunc = TruncDay if group_by == "day" else TruncMonth
        rows = (invoices.annotate(period=trunc("date")).values("period")
                .annotate(invoices=Count("id"), net=Sum("net_amount"), discount=Sum("discount"),
                          received=Sum("paid_amount"), balance=Sum("balance")).order_by("period"))
        out = [{"key": r["period"].strftime("%d/%m/%Y" if group_by == "day" else "%m/%Y"), **r} for r in rows]
        for r in out:
            r.pop("period", None)
    elif group_by == "salesperson":
        rows = (invoices.values("salesperson__username").annotate(
            invoices=Count("id"), net=Sum("net_amount"), discount=Sum("discount"), received=Sum("paid_amount"),
            balance=Sum("balance")).order_by("-net"))
        out = [{"key": r.pop("salesperson__username") or "-", **r} for r in rows]
    elif group_by == "customer":
        rows = (invoices.values("customer__name").annotate(
            invoices=Count("id"), net=Sum("net_amount"), discount=Sum("discount"), received=Sum("paid_amount"),
            balance=Sum("balance")).order_by("-net"))
        out = [{"key": r.pop("customer__name") or "Walk-in", **r} for r in rows]
    elif group_by == "category":
        rows = (lines.values("stock_item__category").annotate(
            invoices=Count("invoice", distinct=True), items=Count("id"), weight=Sum("weight"), net=Sum("line_total"),
            profit=Sum("profit")).order_by("-net"))
        out = [{"key": r.pop("stock_item__category") or "Misc", **r} for r in rows]
    else:
        raise ValueError("group_by must be day, month, category, salesperson or customer")
    totals = invoices.aggregate(invoices=Count("id"), net=Sum("net_amount"), discount=Sum("discount"),
                                received=Sum("paid_amount"), balance=Sum("balance"))
    totals["profit"] = _z(lines.aggregate(p=Sum("profit"))["p"]) - _z(totals["discount"])
    return {"group_by": group_by, "rows": out, "totals": totals}


def expenses_report(date_from, date_to, include_private=True):
    entries = _entries(date_from, date_to).filter(type="E")
    if not include_private:
        entries = entries.filter(hoa__is_private=False)
    rows = [
        {"head": r["hoa__name"], "sub_head": r["sub_hoa__name"] or "", "group": r["hoa__report_group"] or "",
         "count": r["count"], "total": r["total"]}
        for r in entries.values("hoa__name", "sub_hoa__name", "hoa__report_group")
        .annotate(total=Sum("amount"), count=Count("id")).order_by("hoa__name", "sub_hoa__name")
    ]
    by_group = {}
    for r in rows:
        by_group[r["group"] or "other"] = by_group.get(r["group"] or "other", ZERO) + r["total"]
    return {
        "rows": rows, "by_group": by_group,
        "home_total": by_group.get("home", ZERO),
        "shop_total": sum((v for k, v in by_group.items() if k not in DRAWINGS_GROUPS | {"investors"}), ZERO),
        "total": sum((r["total"] for r in rows), ZERO),
    }


def account_summary(date_from, date_to):
    """Provisional Income-Summary accounts (definitions pending owner confirmation, spec section 11)."""
    from refining.services import refine_balance
    from refining.models import RefineLot
    from parties.models import SupplierTransaction

    pl = profit_loss(date_from, date_to)
    lots = RefineLot.objects.filter(date__gte=date_from, date__lte=date_to)
    refine = {
        "lots": lots.count(),
        "weight_sent": _z(lots.aggregate(t=Sum("weight_sent"))["t"]),
        "pasa_expected": _z(lots.aggregate(t=Sum("expected_pasa"))["t"]),
        "pasa_returned": _z(lots.aggregate(t=Sum("pasa_returned"))["t"]),
        "cost": _z(lots.aggregate(t=Sum("cost"))["t"]),
        "pool": refine_balance(),
    }
    purchases = SupplierTransaction.objects.filter(is_voided=False, date__gte=date_from, date__lte=date_to)
    shop_purchase = {
        "purchased": _z(purchases.filter(type__in=["purchase", "labour"]).aggregate(t=Sum("amount"))["t"]),
        "paid_to_suppliers": _z(purchases.filter(type="payment").aggregate(t=Sum("amount"))["t"]),
        "returned": _z(purchases.filter(type="return").aggregate(t=Sum("amount"))["t"]),
        "owed_now": _z(Supplier.objects.aggregate(t=Sum("balance"))["t"]),
    }
    entries = _entries(date_from, date_to)
    investor_profit = _z(entries.filter(hoa__report_group="investors", type="E",
                                        hoa__name="Investor Profit").aggregate(t=Sum("amount"))["t"])
    retention = {
        "net_profit": pl["net_profit"],
        "investor_profit_paid": investor_profit,
        "drawings": pl["total_drawings"],
        "retained": pl["net_profit"] - investor_profit - pl["total_drawings"],
    }
    return {"date_from": date_from, "date_to": date_to, "refine_account": refine, "shop_purchase_account": shop_purchase,
            "profit_retention_account": retention, "provisional": True}


def cash_balances(date=None):
    date = date or timezone.localdate()
    return {acc: v["closing"] for acc, v in cashbook.day_summary(date)["breakdown"].items()}


def dashboard(user):
    today = timezone.localdate()
    rate = latest_rate()
    today_inv = _live_invoices(today, today)
    t = today_inv.aggregate(count=Count("id"), net=Sum("net_amount"), received=Sum("paid_amount"))
    in_stock = StockItem.objects.filter(status=StockItem.Status.IN_STOCK)
    gold = in_stock.filter(metal=StockItem.Metal.GOLD).aggregate(p=Sum("pasa"), n=Count("id"))
    balances = cash_balances(today)
    data = {
        "date": today,
        "gold_rate": {"date": rate.date, "buy": rate.buy_rate_per_tola, "sell": rate.sell_rate_per_tola,
                      "is_today": rate.date == today} if rate else None,
        "today_sales": {"count": t["count"], "net": _z(t["net"]), "received": _z(t["received"])},
        "cash_in_hand": balances.get("shop_cash", ZERO),
        "cash_accounts": balances,
        "stock": {"items": in_stock.count(), "gold_items": gold["n"], "gold_pasa": _z(gold["p"]),
                  "value_at_today": calc.value_of_pasa(_z(gold["p"]), rate.sell_rate_per_tola) if rate else None},
        "outstanding_receivables": _z(Customer.objects.filter(balance__gt=0).aggregate(t=Sum("balance"))["t"]),
        "customers_with_balance": Customer.objects.filter(balance__gt=0).count(),
        "pending_old_gold": _z(OldGoldIntake.objects.filter(status="pending").exclude(invoice__status="voided")
                               .aggregate(p=Sum("pasa"))["p"]),
        "day_locked": cashbook.is_day_locked(today),
        "recent_invoices": list(_live_invoices().select_related("customer").order_by("-created_at")[:8].values(
            "id", "number", "date", "net_amount", "balance", "status", "customer__name", "customer_name")),
    }
    start = today - datetime.timedelta(days=29)
    by_day = {r["date"]: r["net"] for r in Invoice.objects.exclude(status="voided").filter(date__gte=start)
              .values("date").annotate(net=Sum("net_amount"))}
    # Every day appears (zero when there were no sales) so the chart's time axis is continuous.
    data["sales_30_days"] = [{"date": start + datetime.timedelta(days=i),
                              "net": by_day.get(start + datetime.timedelta(days=i), ZERO)} for i in range(30)]
    if user.can_view_profit:
        data["stock"]["cost"] = _z(in_stock.aggregate(c=Sum("total_cost"))["c"])
        month_start = today.replace(day=1)
        pl = profit_loss(month_start, today)
        data["month"] = {"net_sales": pl["net_sales"], "gross_profit": pl["gross_profit"],
                         "expenses": pl["total_expenses"], "net_profit": pl["net_profit"]}
        data["payables"] = _z(Supplier.objects.filter(balance__gt=0).aggregate(t=Sum("balance"))["t"])
    return data


def zakat(date, basis="sell", deduct_liabilities=True):
    """Zakat due = (stock + cash + receivables [+ pending gold] - liabilities) x rate%."""
    shop = ShopSettings.load()
    rate = GoldRate.for_date(date)
    if not rate:
        raise ValueError("No gold rate on or before that date.")
    per_tola = rate.sell_rate_per_tola if basis == "sell" else rate.buy_rate_per_tola
    # Stock that was in hand on that date: purchased on/before it and not sold by then.
    stock = StockItem.objects.filter(Q(purchase_date__lte=date) | Q(purchase_date__isnull=True)).filter(
        Q(status=StockItem.Status.IN_STOCK) | Q(sold_date__gt=date))
    gold = stock.filter(metal=StockItem.Metal.GOLD)
    if basis == "cost":
        stock_value = _z(stock.aggregate(t=Sum("total_cost"))["t"])
    else:
        gold_pasa = _z(gold.aggregate(p=Sum("pasa"))["p"])
        other_cost = _z(stock.exclude(metal=StockItem.Metal.GOLD).aggregate(t=Sum("total_cost"))["t"])
        stock_value = calc.value_of_pasa(gold_pasa, per_tola) + other_cost
    pending_pasa = _z(OldGoldIntake.objects.filter(status__in=["pending", "sent_to_refine"], invoice__date__lte=date)
                      .exclude(invoice__status="voided").aggregate(p=Sum("pasa"))["p"])
    pending_value = calc.value_of_pasa(pending_pasa, per_tola)
    cash = cashbook.balance_as_of(date)
    receivables = _z(Customer.objects.filter(balance__gt=0).aggregate(t=Sum("balance"))["t"])
    liabilities = _z(Supplier.objects.filter(balance__gt=0).aggregate(t=Sum("balance"))["t"]) if deduct_liabilities else ZERO
    zakatable = stock_value + pending_value + cash + receivables - liabilities
    due = calc.q_money(max(zakatable, ZERO) * shop.zakat_rate_percent / Decimal("100"))
    return {
        "date": date, "basis": basis, "rate_per_tola": per_tola, "rate_date": rate.date,
        "stock_value": stock_value, "stock_items": stock.count(), "old_gold_value": pending_value,
        "cash": cash, "receivables": receivables, "liabilities": liabilities,
        "zakatable_total": zakatable, "zakat_rate_percent": shop.zakat_rate_percent, "zakat_due": due,
        "note": "Receivables and liabilities use current balances. Method pending owner confirmation.",
    }
