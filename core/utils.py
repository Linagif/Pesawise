"""Small helpers: money rounding, date ranges, safe redirects."""
import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils.http import url_has_allowed_host_and_scheme

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    """Return value as a Decimal rounded to 2 places (None -> 0.00)."""
    if value is None:
        return ZERO
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def month_range(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def week_range(day):
    """Monday to Sunday week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def add_months(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def safe_next(request, default):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return default


def safe_date(value):
    """Parse 'YYYY-MM-DD'. Returns None for empty, malformed OR impossible dates (e.g. 2020-13-45)."""
    from django.utils.dateparse import parse_date
    try:
        return parse_date(value or "")
    except ValueError:
        return None
