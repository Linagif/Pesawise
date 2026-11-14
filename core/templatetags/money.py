from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def kes(value):
    """1234.5 -> 'KSh 1,234.50'"""
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "KSh 0.00"
    sign = "-" if amount < 0 else ""
    return f"{sign}KSh {abs(amount):,.2f}"


@register.filter
def pct(value):
    return "—" if value is None else f"{value}%"
