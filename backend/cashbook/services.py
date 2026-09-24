"""Posting to the cash book from other modules, plus day-close logic."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.utils import timezone

from core import audit
from core.exceptions import BusinessRuleError
from core.models import AuditLog, HeadOfAccount, ShopSettings

from .models import CashBookEntry, DayClose

I = CashBookEntry.Type.INCOME
E = CashBookEntry.Type.EXPENDITURE

# System heads of account used for automatic postings: key -> (name, type, report_group, is_private)
SYSTEM_HEADS = {
    "sale": ("Sale", I, "sales", False),
    "advance": ("Adv", I, "sales", False),
    "customer_payment": ("Customer Receipt", I, "sales", False),
    "supplier_payment": ("Supplier Payment", E, "shop_purchase", False),
    "karigar_payment": ("Karigar Payment", E, "shop_purchase", False),
    "refine": ("Refine", E, "refine", False),
    "investment": ("Investment", I, "investors", True),
    "investor_withdrawal": ("Investor Withdrawal", E, "investors", True),
    "investor_profit": ("Investor Profit", E, "investors", True),
    "reversal_income": ("Reversal", I, "adjustments", False),
    "reversal_expense": ("Reversal", E, "adjustments", False),
}

DEFAULT_HEADS = [
    # name, type, report_group, is_private, sub-heads
    ("Sale", I, "sales", False, []),
    ("Adv", I, "sales", False, []),
    ("Customer Receipt", I, "sales", False, []),
    ("OJ", I, "oj", False, []),
    ("Salami", I, "other_income", False, []),
    ("Investment", I, "investors", True, []),
    ("SDTD", E, "shop_expenses", False, ["Tea", "Electricity", "Rent", "Salary", "Stationery", "Repair", "Misc"]),
    ("Home", E, "home", True, ["Grocery", "Utilities", "School", "Medical", "Misc"]),
    ("Zakat", E, "zakat", True, []),
    ("Refine", E, "refine", False, []),
    ("Shopjew", E, "shopjew", False, []),
    ("Supplier Payment", E, "shop_purchase", False, []),
    ("Karigar Payment", E, "shop_purchase", False, []),
    ("Investor Withdrawal", E, "investors", True, []),
    ("Investor Profit", E, "investors", True, []),
]


def system_head(key):
    name, type_, group, private = SYSTEM_HEADS[key]
    head, _ = HeadOfAccount.objects.get_or_create(
        name=name, type=type_, parent=None,
        defaults={"report_group": group, "is_private": private},
    )
    return head


def ensure_default_heads():
    for name, type_, group, private, subs in DEFAULT_HEADS:
        head, _ = HeadOfAccount.objects.get_or_create(
            name=name, type=type_, parent=None, defaults={"report_group": group, "is_private": private}
        )
        for sub in subs:
            HeadOfAccount.objects.get_or_create(
                name=sub, type=type_, parent=head, defaults={"report_group": group, "is_private": private}
            )


def is_day_locked(date):
    return DayClose.objects.filter(date=date, is_locked=True).exists()


def assert_day_open(date):
    if is_day_locked(date):
        raise BusinessRuleError(
            f"The cash book for {date:%d/%m/%Y} is closed. Ask the owner to reopen the day first."
        )


def validate_cash_account(name):
    accounts = ShopSettings.load().cash_accounts
    if name not in accounts:
        raise BusinessRuleError(f"Unknown cash account '{name}'. Valid accounts: {', '.join(accounts)}.")


def post_entry(*, key, date, amount, user, source_type, source_id=None, party="", detail="",
               cash_account="shop_cash", debited_to="Shop", notes="", book_no="", page_no="", type_override=None):
    """Create an automatic cash book entry under a system head of account."""
    assert_day_open(date)
    validate_cash_account(cash_account)
    head = system_head(key)
    entry = CashBookEntry.objects.create(
        date=date, type=type_override or head.type, hoa=head, amount=amount, source_type=source_type,
        source_id=source_id, party=party[:200], detail=detail[:100], cash_account=cash_account,
        debited_to=debited_to, notes=notes, book_no=book_no, page_no=page_no, created_by=user, updated_by=user,
    )
    audit.log_create(user, entry, note=f"Auto-posted from {source_type}")
    return entry


def void_or_reverse(entry, user, reason):
    """Void an entry; if its day is locked, post a reversing entry today instead."""
    if entry.is_voided:
        return None
    if is_day_locked(entry.date):
        today = timezone.localdate()
        assert_day_open(today)
        reverse_type = E if entry.type == I else I
        head = system_head("reversal_expense" if reverse_type == E else "reversal_income")
        rev = CashBookEntry.objects.create(
            date=today, type=reverse_type, hoa=head, amount=entry.amount, source_type=CashBookEntry.Source.REVERSAL,
            source_id=entry.id, party=entry.party, detail=entry.detail, cash_account=entry.cash_account,
            debited_to=entry.debited_to, notes=f"Reversal of {entry.date:%d/%m/%Y} entry: {reason}",
            created_by=user, updated_by=user,
        )
        audit.log_create(user, rev, note=f"Reversal: {reason}")
        return rev
    old = audit.snapshot(entry)
    entry.is_voided = True
    entry.void_reason = reason[:200]
    entry.updated_by = user
    entry.save(update_fields=["is_voided", "void_reason", "updated_by", "updated_at"])
    audit.log(user, AuditLog.Action.VOID, entry, audit.diff(old, audit.snapshot(entry)), note=reason)
    return entry


def _signed_sum(qs):
    return qs.aggregate(
        t=Sum(Case(When(type=I, then=F("amount")), default=-F("amount"), output_field=DecimalField()))
    )["t"] or Decimal("0")


def balances_before(date, cash_account=None):
    qs = CashBookEntry.objects.filter(date__lt=date, is_voided=False)
    if cash_account:
        qs = qs.filter(cash_account=cash_account)
    return _signed_sum(qs)


def balance_as_of(date, cash_account=None):
    qs = CashBookEntry.objects.filter(date__lte=date, is_voided=False)
    if cash_account:
        qs = qs.filter(cash_account=cash_account)
    return _signed_sum(qs)


def day_summary(date):
    """Opening, in, out and closing — overall and per cash account."""
    accounts = list(ShopSettings.load().cash_accounts)
    day = CashBookEntry.objects.filter(date=date, is_voided=False)
    used = set(day.values_list("cash_account", flat=True)) | set(
        CashBookEntry.objects.filter(date__lt=date).values_list("cash_account", flat=True).distinct()
    )
    for acc in sorted(used):
        if acc not in accounts:
            accounts.append(acc)
    breakdown = {}
    for acc in accounts:
        opening = balances_before(date, acc)
        inc = day.filter(cash_account=acc, type=I).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        exp = day.filter(cash_account=acc, type=E).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        breakdown[acc] = {"opening": opening, "income": inc, "expenditure": exp, "closing": opening + inc - exp}
    opening = sum((b["opening"] for b in breakdown.values()), Decimal("0"))
    income = sum((b["income"] for b in breakdown.values()), Decimal("0"))
    expenditure = sum((b["expenditure"] for b in breakdown.values()), Decimal("0"))
    return {
        "date": date,
        "opening_balance": opening,
        "total_income": income,
        "total_expenditure": expenditure,
        "closing_balance": opening + income - expenditure,
        "breakdown": breakdown,
        "entry_count": day.count(),
        "is_locked": is_day_locked(date),
    }


def _json_breakdown(breakdown):
    return {acc: {k: str(v) for k, v in vals.items()} for acc, vals in breakdown.items()}


@transaction.atomic
def close_day(date, user, counted_cash=None, notes=""):
    if date > timezone.localdate():
        raise BusinessRuleError("Cannot close a future day.")
    if is_day_locked(date):
        raise BusinessRuleError(f"{date:%d/%m/%Y} is already closed.")
    s = day_summary(date)
    dc, _ = DayClose.objects.update_or_create(
        date=date,
        defaults=dict(
            opening_balance=s["opening_balance"], total_income=s["total_income"],
            total_expenditure=s["total_expenditure"], closing_balance=s["closing_balance"],
            breakdown=_json_breakdown(s["breakdown"]), counted_cash=counted_cash, notes=notes,
            is_locked=True, locked_by=user, locked_at=timezone.now(),
        ),
    )
    CashBookEntry.objects.filter(date=date).update(day_locked=True)
    audit.log(user, AuditLog.Action.LOCK, dc, {"closing_balance": str(dc.closing_balance)}, note="Day closed")
    return dc


@transaction.atomic
def reopen_day(date, user, reason=""):
    dc = DayClose.objects.select_for_update().filter(date=date, is_locked=True).first()
    if not dc:
        raise BusinessRuleError(f"{date:%d/%m/%Y} is not closed.")
    dc.is_locked = False
    dc.reopened_by = user
    dc.reopened_at = timezone.now()
    dc.save()
    CashBookEntry.objects.filter(date=date).update(day_locked=False)
    audit.log(user, AuditLog.Action.UNLOCK, dc, note=reason or "Day reopened")
    return dc
