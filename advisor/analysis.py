"""Financial Health analysis: deterministic, testable calculations over ONE student's records.

Principles
  * Money is always Decimal. Percentages are rounded to 1 decimal place (ROUND_HALF_UP).
  * Every function says when it has NOT got enough data (available=False / None) instead of guessing.
  * Functions return facts and numbers. Turning them into sentences happens in build_health_report().
  * Thresholds that decide a status are named constants below, so they are easy to find, explain and test.
"""
import calendar
import re
import statistics
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Sum

from core.models import Category
from core.utils import ZERO, add_months, money, month_range
from dashboard import services as svc
from expenses.models import Expense

# ---- named thresholds (guidelines, not universal rules; the page says so) ----
SAVINGS_RATE_GOOD = Decimal("10")          # % of income moved to savings
ESSENTIAL_SHARE_OF_INCOME_WATCH = Decimal("80")   # % of income already needed for essentials
EMERGENCY_MONTHS_GOOD = Decimal("3")       # months of essential spending covered by savings
EMERGENCY_MONTHS_CONCERN = Decimal("1")
CHANGE_PCT_MIN = Decimal("20")             # month-on-month change worth mentioning...
CHANGE_KES_MIN = Decimal("200")            # ...and it must also be at least this many shillings
SMALL_PURCHASE_LIMIT = Decimal("100")      # "small" = KSh 100 or less
SMALL_PURCHASE_MIN_COUNT = 8               # ...and at least this many in 30 days before we mention it
RECURRING_MIN_MONTHS = 3                   # a payment must appear in this many different months
RECURRING_AMOUNT_TOLERANCE = Decimal("0.15")   # amounts within 15% of the typical amount
MIN_EXPENSES_FOR_ANALYSIS = 10             # below this we show a "limited data" notice


def pct(part, whole):
    """part/whole as a percentage with 1 decimal, or None when whole is zero."""
    if not whole:
        return None
    return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def kes(value):
    return f"KSh {Decimal(value):,.2f}"


def _expenses(user, start, end):
    return Expense.objects.filter(user=user, expense_date__gte=start, expense_date__lte=end)


# ---------------------------------------------------------------- periods
def period_bounds(today, which="this"):
    """'this' = this month so far; 'last' = the previous full calendar month."""
    if which == "last":
        y, m = add_months(today.year, today.month, -1)
        start, end = month_range(y, m)
        return start, end, f"{calendar.month_name[m]} {y}"
    start, end = month_range(today.year, today.month)
    return start, min(end, today), "This month so far"


# ---------------------------------------------------------------- 1-2. cash flow & savings rate
def cash_flow(user, start, end):
    income = svc.total_income(user, start, end)
    expenses = svc.total_expenses(user, start, end)
    saved = svc.total_savings_transfers(user, start, end)
    return {"income": income, "expenses": expenses, "saved": saved,
            "net": money(income - expenses),                       # income minus spending
            "savings_rate": pct(saved, income)}                    # None when there is no income


# ---------------------------------------------------------------- 3. essential vs discretionary
def essential_split(user, start, end, income=None):
    rows = (_expenses(user, start, end).values("category__spending_type").annotate(t=Sum("amount")))
    totals = {r["category__spending_type"]: money(r["t"]) for r in rows}
    essential = totals.get(Category.ESSENTIAL, ZERO)
    discretionary = totals.get(Category.DISCRETIONARY, ZERO)
    total = money(essential + discretionary)
    return {"essential": essential, "discretionary": discretionary, "total": total,
            "essential_share": pct(essential, total), "discretionary_share": pct(discretionary, total),
            "essential_pct_of_income": pct(essential, income) if income else None}


# ---------------------------------------------------------------- 4. emergency fund coverage
def emergency_fund(user, today):
    """Total savings / average monthly ESSENTIAL spending over up to 3 recent complete months.
    Returns None if there is no complete month with essential spending to base it on."""
    monthly = []
    for back in (1, 2, 3):
        y, m = add_months(today.year, today.month, -back)
        s, e = month_range(y, m)
        ess = essential_split(user, s, e)["essential"]
        if ess > 0:
            monthly.append(ess)
    if not monthly:
        return None
    avg = money(sum(monthly, ZERO) / len(monthly))
    saved = svc.total_savings(user)
    return {"months": (saved / avg).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "saved": saved,
            "avg_essential": avg, "months_used": len(monthly)}


# ---------------------------------------------------------------- 5. month-over-month category change
def _category_totals(user, start, end):
    rows = _expenses(user, start, end).values("category__name").annotate(t=Sum("amount"))
    return {r["category__name"]: money(r["t"]) for r in rows}


def category_changes(user, today):
    """Compares the last two COMPLETE months (never a partial month against a full one)."""
    ay, am = add_months(today.year, today.month, -1)
    by, bm = add_months(today.year, today.month, -2)
    after = _category_totals(user, *month_range(ay, am))
    before = _category_totals(user, *month_range(by, bm))
    if not after or not before:
        return {"available": False, "reason": "Needs expenses recorded in two full months."}
    rows = []
    for name in set(after) | set(before):
        a, b = after.get(name, ZERO), before.get(name, ZERO)
        diff = a - b
        if abs(diff) < CHANGE_KES_MIN:
            continue
        change = None if b == 0 else pct(diff, b)
        if change is not None and abs(change) < CHANGE_PCT_MIN:
            continue
        rows.append({"category": name, "before": b, "after": a, "diff": diff, "pct": change,
                     "direction": "up" if diff > 0 else "down", "is_new": b == 0})
    rows.sort(key=lambda r: abs(r["diff"]), reverse=True)
    return {"available": True, "rows": rows, "from_label": calendar.month_name[bm], "to_label": calendar.month_name[am]}


# ---------------------------------------------------------------- 6. small purchases that add up
def small_purchases(user, today):
    start = today - timedelta(days=29)
    qs = _expenses(user, start, today)
    total_all = money(qs.aggregate(t=Sum("amount"))["t"])
    small = qs.filter(amount__lte=SMALL_PURCHASE_LIMIT).aggregate(t=Sum("amount"), n=Count("id"))
    count, total = small["n"] or 0, money(small["t"])
    return {"count": count, "total": total, "share": pct(total, total_all), "limit": SMALL_PURCHASE_LIMIT,
            "fired": count >= SMALL_PURCHASE_MIN_COUNT}


# ---------------------------------------------------------------- 7. recurring payments
def _normalise(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def recurring_payments(user, today):
    """Same description, similar amount, in at least 3 different months of the last 6. Shown as 'looks recurring'."""
    ys, ms = add_months(today.year, today.month, -5)
    start = month_range(ys, ms)[0]
    groups = defaultdict(list)
    for e in _expenses(user, start, today).select_related("category").order_by("expense_date"):
        groups[(_normalise(e.description), e.category_id)].append(e)
    found = []
    for items in groups.values():
        months = {(e.expense_date.year, e.expense_date.month) for e in items}
        if len(months) < RECURRING_MIN_MONTHS or len(items) > 2 * len(months):
            continue
        typical = statistics.median([e.amount for e in items])
        if any(abs(e.amount - typical) > typical * RECURRING_AMOUNT_TOLERANCE for e in items):
            continue
        last = items[-1]
        found.append({"description": last.description, "category": last.category.name, "typical": money(typical),
                      "months_seen": len(months), "last_date": last.expense_date,
                      "essential": last.category.spending_type == Category.ESSENTIAL})
    found.sort(key=lambda r: r["typical"], reverse=True)
    return found[:5]


# ---------------------------------------------------------------- report builder
def _indicator(key, title, value, status, explain, evidence="", available=True):
    return {"key": key, "title": title, "value": value, "status": status, "explain": explain,
            "evidence": evidence, "available": available}


def build_health_report(user, today, period="this"):
    start, end, label = period_bounds(today, "last" if period == "last" else "this")
    flow = cash_flow(user, start, end)
    split = essential_split(user, start, end, flow["income"])
    expense_count = Expense.objects.filter(user=user).count()
    indicators, insights = [], []

    # Net cash flow
    if flow["income"] > 0:
        status = "concern" if flow["net"] < 0 else "good"
        verdict = ("You spent more than you recorded as received." if flow["net"] < 0
                   else "You spent less than you received.")
        indicators.append(_indicator(
            "cashflow", "Net cash flow", kes(flow["net"]), status,
            "Income minus spending for the period. A negative number means you spent more than you received, "
            "so the gap came from money you already had or from borrowing.",
            f"{kes(flow['income'])} received − {kes(flow['expenses'])} spent. {verdict}"))
    else:
        indicators.append(_indicator("cashflow", "Net cash flow", "n/a", "info",
                                     "Income minus spending for the period.",
                                     "No income is recorded in this period, so this cannot be worked out.", False))

    # Savings rate
    if flow["savings_rate"] is not None:
        rate = flow["savings_rate"]
        status = "good" if rate >= SAVINGS_RATE_GOOD else "watch"
        indicators.append(_indicator(
            "savings_rate", "Savings rate", f"{rate}%", status,
            "The share of your income you moved into savings goals. A common guideline is to aim for around 10% or "
            "more, but the right level depends on your circumstances.",
            f"{kes(flow['saved'])} saved out of {kes(flow['income'])} received."))
    else:
        indicators.append(_indicator("savings_rate", "Savings rate", "n/a", "info",
                                     "The share of your income you moved into savings goals.",
                                     "No income is recorded in this period.", False))

    # Essential vs discretionary
    if split["total"] > 0:
        ess_income = split["essential_pct_of_income"]
        status = "watch" if (ess_income is not None and ess_income >= ESSENTIAL_SHARE_OF_INCOME_WATCH) else "info"
        evidence = (f"Essentials {kes(split['essential'])} ({split['essential_share']}% of spending), "
                    f"discretionary {kes(split['discretionary'])} ({split['discretionary_share']}%).")
        if ess_income is not None:
            evidence += f" Essentials take {ess_income}% of the income you received."
        indicators.append(_indicator(
            "split", "Essential vs discretionary", f"{split['essential_share']}% essential", status,
            "Essentials are needs such as rent, food and transport; discretionary spending is wants. This split follows "
            "how your categories are labelled (you can change your own under Categories), so treat it as a guide.",
            evidence))
    else:
        indicators.append(_indicator("split", "Essential vs discretionary", "n/a", "info",
                                     "How your spending divides between needs and wants.",
                                     "No expenses are recorded in this period.", False))

    # Emergency fund
    fund = emergency_fund(user, today)
    if fund:
        months = fund["months"]
        status = "good" if months >= EMERGENCY_MONTHS_GOOD else ("concern" if months < EMERGENCY_MONTHS_CONCERN else "watch")
        indicators.append(_indicator(
            "emergency", "Emergency fund coverage", f"{months} months", status,
            "How many months of essential spending your total savings could cover if your income stopped. Many advisers "
            "suggest 3 or more months, though students often start smaller. All your savings goals are counted together.",
            f"{kes(fund['saved'])} saved ÷ {kes(fund['avg_essential'])} average monthly essentials "
            f"(based on {fund['months_used']} full month{'s' if fund['months_used'] != 1 else ''})."))
    else:
        indicators.append(_indicator("emergency", "Emergency fund coverage", "n/a", "info",
                                     "How many months of essential spending your savings could cover.",
                                     "Needs at least one full past month with essential spending recorded.", False))

    # ---- insights, each tied to the figures behind it
    changes = category_changes(user, today)
    if changes["available"]:
        for r in changes["rows"][:3]:
            if r["is_new"]:
                text = (f"You spent {kes(r['after'])} on {r['category']} in {changes['to_label']}, "
                        f"with nothing recorded in {changes['from_label']}.")
                level = "info"
            elif r["direction"] == "up":
                text = (f"{r['category']} spending rose {r['pct']}% from {kes(r['before'])} in {changes['from_label']} "
                        f"to {kes(r['after'])} in {changes['to_label']}. Check whether this is a one-off or a new pattern.")
                level = "warning"
            else:
                text = (f"{r['category']} spending fell {abs(r['pct'])}% from {kes(r['before'])} in {changes['from_label']} "
                        f"to {kes(r['after'])} in {changes['to_label']}.")
                level = "success"
            insights.append({"level": level, "title": f"{r['category']}: change from {changes['from_label']}", "text": text})

    sp = small_purchases(user, today)
    if sp["fired"]:
        insights.append({"level": "info", "title": "Small purchases add up",
                         "text": f"In the last 30 days you made {sp['count']} purchases of {kes(sp['limit'])} or less, "
                                 f"adding up to {kes(sp['total'])} ({sp['share']}% of your spending). "
                                 "Each is small, so it may be worth seeing whether any can be combined or skipped."})

    for r in recurring_payments(user, today):
        closing = ("This looks like a regular essential cost, so it is useful to include in your budget." if r["essential"] else
                   "If it is a subscription or regular bill, check that you still want it.")
        insights.append({"level": "info", "title": f"Looks recurring: {r['description']}",
                         "text": f"“{r['description']}” ({r['category']}) appeared in {r['months_seen']} different months, "
                                 f"usually around {kes(r['typical'])}. Last seen {r['last_date']:%d %b %Y}. {closing}"})

    notices = []
    if expense_count < MIN_EXPENSES_FOR_ANALYSIS:
        notices.append("You have recorded only a few expenses so far, so some indicators and insights are hidden or "
                       "may change as you add more. Keep recording and this page will become more useful.")
    if not changes["available"]:
        notices.append("Month-to-month comparisons need expenses recorded in two full months.")

    return {"period": period, "period_label": label, "start": start, "end": end, "flow": flow, "split": split,
            "indicators": indicators, "insights": insights, "notices": notices, "expense_count": expense_count}
