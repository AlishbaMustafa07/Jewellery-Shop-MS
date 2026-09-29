"""Template filters for PKR money, weights and DD/MM/YYYY dates."""
import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter
def pkr(value):
    d = _dec(value)
    if d is None:
        return value if value is not None else ""
    return f"{d.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


@register.filter
def wt(value):
    d = _dec(value)
    if d is None:
        return ""
    return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


@register.filter
def is_number(value):
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


@register.filter
def cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, datetime.date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        if value == value.to_integral_value() or abs(value) >= 1000:
            return pkr(value)
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    return value
