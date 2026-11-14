"""All financial calculations live here (never in templates or views).

Rules (see docs/SRS.md section 8):
  Available balance = Total income - Total expenses - Savings contributions
  Savings are stored ONLY as SavingsContribution (never as Expense) so they are subtracted once.
  All money uses Decimal, rounded to 2 places with ROUND_HALF_UP.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum

from budgets.models import Budget
from core.models import Category
from core.utils import ZERO, add_months, money, month_range, week_range
from expenses.models import Expense
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal

WARNING_AT = Decimal("80")
HUNDRED = Decimal("100")


def _total(qs):
    return money(qs.aggregate(t=Sum("amount"))["t"])


def _between(qs, field, start, end):
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


# ---------- core totals ----------
def total_income(user, start=None, end=None):
    return _total(_between(Income.objects.filter(user=user), "date_received", start, end))


def total_expenses(user, start=None, end=None):
    return _total(_between(Expense.objects.filter(user=user), "expense_date", start, end))


def total_savings_transfers(user, start=None, end=None):
    qs = SavingsContribution.objects.filter(goal__user=user)
    return _total(_between(qs, "contribution_date", start, end))


def available_balance(user, start=None, end=None):
    return money(total_income(user, start, end) - total_expenses(user, start, end)
                 - total_savings_transfers(user, start, end))


def total_savings(user):
    """Sum of every goal's current amount (starting amount + contributions)."""
    return money(sum((g.current_amount for g in SavingsGoal.objects.filter(user=user)), ZERO))


# ---------- budget maths ----------
def utilization(actual, allocated):
    """Percent used. Zero budget: 0% if nothing spent, otherwise None ('unbudgeted')."""
    if allocated and allocated > 0:
        return (actual / allocated * HUNDRED).quantize(Decimal("0.1"))
    return Decimal("0.0") if actual <= 0 else None


def status_for(actual, allocated):
    pct = utilization(actual, allocated)
    if pct is None or pct > HUNDRED:
        return "over"
    return "warning" if pct >= WARNING_AT else "ok"


COLORS = {"ok": "success", "warning": "warning", "over": "danger"}


def _row(name, allocated, actual, category=None, allocation=None):
    pct = utilization(actual, allocated)
    st = status_for(actual, allocated)
    width = 100 if pct is None else int(min(HUNDRED, pct))
    return {"name": name, "category": category, "allocation": allocation, "allocated": allocated,
            "actual": actual, "remaining": money(allocated - actual), "pct": pct, "status": st,
            "color": COLORS[st], "width": width}


def budget_progress(budget):
    """Per-category rows plus totals for one monthly budget."""
    start, end = month_range(budget.year, budget.month)
    user = budget.user
    month_expenses = Expense.objects.filter(user=user, expense_date__gte=start, expense_date__lte=end)
    by_cat = {r["category_id"]: money(r["t"]) for r in month_expenses.values("category_id").annotate(t=Sum("amount"))}
    savings_actual = total_savings_transfers(user, start, end)
    rows, budgeted_ids, has_savings_line = [], set(), False
    for a in budget.allocations.select_related("category"):
        if a.category.category_type == Category.SAVINGS:
            actual, has_savings_line = savings_actual, True
        else:
            actual = by_cat.get(a.category_id, ZERO)
            budgeted_ids.add(a.category_id)
        rows.append(_row(a.category.name, money(a.allocated_amount), actual, a.category, a))
    unbudgeted = money(sum((v for k, v in by_cat.items() if k not in budgeted_ids), ZERO))
    total_allocated = money(sum((r["allocated"] for r in rows), ZERO))
    total_actual = money(sum((r["actual"] for r in rows), ZERO) + unbudgeted)
    pct = utilization(total_actual, total_allocated)
    status = status_for(total_actual, total_allocated)
    return {"rows": rows, "total_allocated": total_allocated, "total_actual": total_actual,
            "remaining": money(total_allocated - total_actual), "unbudgeted": unbudgeted,
            "pct": pct, "has_savings_line": has_savings_line, "status": status, "color": COLORS[status],
            "width": 100 if pct is None else int(min(HUNDRED, pct))}


def category_budget_alert(user, category, day):
    """After recording an expense: warn if its category is near/over the month's limit."""
    budget = Budget.objects.filter(user=user, month=day.month, year=day.year).first()
    if not budget:
        return None
    alloc = budget.allocations.filter(category=category).first()
    if not alloc:
        return None
    start, end = month_range(day.year, day.month)
    actual = _total(Expense.objects.filter(user=user, category=category, expense_date__gte=start, expense_date__lte=end))
    allocated = money(alloc.allocated_amount)
    pct = utilization(actual, allocated)
    if pct is None or pct > HUNDRED:
        over = money(actual - allocated)
        return ("danger", f"Over budget: {category.name} is now {over:,.2f} above its KSh {allocated:,.2f} limit.")
    if pct >= WARNING_AT:
        return ("warning", f"Careful: you have used {pct}% of your {category.name} budget.")
    return None


# ---------- daily / weekly / monthly ----------
def spend_totals(user, day):
    ws, we = week_range(day)
    ms, me = month_range(day.year, day.month)
    return {"day": total_expenses(user, day, day), "week": total_expenses(user, ws, we),
            "month": total_expenses(user, ms, me), "week_start": ws, "week_end": we}


def spending_by_category(user, start=None, end=None):
    qs = _between(Expense.objects.filter(user=user), "expense_date", start, end)
    rows = [{"name": r["category__name"], "total": money(r["t"]), "count": r["n"]}
            for r in qs.values("category__name").annotate(t=Sum("amount"), n=Count("id")).order_by("-t")]
    grand = sum((r["total"] for r in rows), ZERO)
    for r in rows:
        r["share"] = int(r["total"] / grand * 100) if grand else 0
    return rows


def income_by_source(user, start=None, end=None):
    qs = _between(Income.objects.filter(user=user), "date_received", start, end)
    return [{"name": r["source__name"], "total": money(r["t"]), "count": r["n"]}
            for r in qs.values("source__name").annotate(t=Sum("amount"), n=Count("id")).order_by("-t")]


def daily_summary(user, day):
    items = Expense.objects.filter(user=user, expense_date=day).select_related("category")
    total = _total(items)
    prof = getattr(user, "profile", None)
    target = prof.daily_spending_target if prof else None
    return {"total": total, "count": items.count(), "highest": items.order_by("-amount").first(),
            "by_category": spending_by_category(user, day, day), "target": target,
            "remaining_target": money(target - total) if target else None}


def average_daily_spend_before(user, day):
    """Average spend per day (days with spending) earlier in the same month -> (average, number_of_days)."""
    start, _ = month_range(day.year, day.month)
    if day <= start:
        return ZERO, 0
    qs = Expense.objects.filter(user=user, expense_date__gte=start, expense_date__lt=day)
    days = qs.values("expense_date").annotate(t=Sum("amount"))
    totals = [r["t"] for r in days]
    if not totals:
        return ZERO, 0
    return money(sum(totals) / len(totals)), len(totals)


def monthly_series(user, today, months=6):
    out = []
    for i in range(months - 1, -1, -1):
        y, m = add_months(today.year, today.month, -i)
        s, e = month_range(y, m)
        out.append({"label": s.strftime("%b %Y"), "income": total_income(user, s, e),
                    "expenses": total_expenses(user, s, e), "savings": total_savings_transfers(user, s, e)})
    return out


def daily_series(user, start, end):
    qs = Expense.objects.filter(user=user, expense_date__gte=start, expense_date__lte=end)
    totals = {r["expense_date"]: money(r["t"]) for r in qs.values("expense_date").annotate(t=Sum("amount"))}
    out, d = [], start
    while d <= end:
        out.append({"date": d, "total": totals.get(d, ZERO)})
        d += timedelta(days=1)
    return out
