"""Builds the data for a report. Used by the HTML page AND by the CSV/PDF exports,
so the three can never disagree with each other."""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from budgets.models import Budget
from core.utils import money, month_range, safe_date, week_range
from expenses.models import Expense
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal

from . import services as svc

REPORT_KINDS = [("daily", "Daily summary"), ("weekly", "Weekly summary"), ("monthly", "Monthly summary"),
                ("income", "Income report"), ("expense", "Expense report"), ("savings", "Savings report"),
                ("budget", "Budget performance")]


def build_report(user, params):
    """params is request.GET. Bad or missing input falls back to safe defaults."""
    today = timezone.localdate()
    kind = params.get("kind", "monthly")
    if kind not in dict(REPORT_KINDS):
        kind = "monthly"
    anchor = min(safe_date(params.get("date")) or today, today)
    if kind == "daily":
        start = end = anchor
    elif kind == "weekly":
        start, end = week_range(anchor)
    elif kind in ("monthly", "budget"):
        start, end = month_range(anchor.year, anchor.month)
    else:
        ms, me = month_range(today.year, today.month)
        start = safe_date(params.get("start")) or ms
        end = safe_date(params.get("end")) or me
        if end < start:
            start, end = end, start
    inc, exp, sav = (svc.total_income(user, start, end), svc.total_expenses(user, start, end),
                     svc.total_savings_transfers(user, start, end))
    expenses = Expense.objects.filter(user=user, expense_date__gte=start, expense_date__lte=end).select_related("category")
    unplanned = money(expenses.filter(is_planned=False).aggregate(t=Sum("amount"))["t"])
    budget = Budget.objects.filter(user=user, month=start.month, year=start.year).first() if kind == "budget" else None
    return {
        "kinds": REPORT_KINDS, "kind": kind, "kind_label": dict(REPORT_KINDS)[kind], "anchor": anchor,
        "start": start, "end": end, "income_total": inc, "expense_total": exp, "savings_total": sav,
        "net": money(inc - exp - sav), "unplanned_total": unplanned,
        "by_category": svc.spending_by_category(user, start, end), "by_source": svc.income_by_source(user, start, end),
        "expenses": expenses[:200], "expense_count": expenses.count(),
        "incomes": Income.objects.filter(user=user, date_received__gte=start, date_received__lte=end).select_related("source")[:200],
        "contributions": SavingsContribution.objects.filter(
            goal__user=user, contribution_date__gte=start, contribution_date__lte=end).select_related("goal"),
        "goals": SavingsGoal.objects.filter(user=user),
        "per_day": svc.daily_series(user, start, end) if kind in ("weekly", "monthly") else [],
        "budget": budget, "prog": svc.budget_progress(budget) if budget else None,
        "summary": svc.daily_summary(user, start) if kind == "daily" else None,
    }


def report_sections(ctx):
    """Turn a report into plain tables: [(title, header_row, rows)]. CSV and PDF both render these."""
    kind = ctx["kind"]
    S = []
    S.append(("Summary", ["Item", "Amount"], [
        ["Income received", ctx["income_total"]], ["Expenses", ctx["expense_total"]],
        ["Moved to savings", ctx["savings_total"]], ["Left over in this period", ctx["net"]]]))
    if kind == "budget" and ctx["prog"]:
        p = ctx["prog"]
        rows = [[r["name"], r["allocated"], r["actual"], r["remaining"],
                 "no limit" if r["pct"] is None else f"{r['pct']}%",
                 {"over": "Over budget", "warning": "Near limit", "ok": "On track"}[r["status"]]] for r in p["rows"]]
        rows.append(["Total", p["total_allocated"], p["total_actual"], p["remaining"],
                     "-" if p["pct"] is None else f"{p['pct']}%", ""])
        S.append((f"Budget performance: {ctx['budget'].label}", ["Category", "Limit", "Actual", "Remaining", "Used", "Status"], rows))
    if ctx["per_day"]:
        S.append(("Spending per day", ["Date", "Spent"], [[d["date"].strftime("%a %d %b %Y"), d["total"]] for d in ctx["per_day"]]))
    if kind not in ("savings", "budget"):
        if kind != "income":
            S.append(("Expenses by category", ["Category", "Transactions", "Total"],
                      [[c["name"], c["count"], c["total"]] for c in ctx["by_category"]]))
        if kind != "expense":
            S.append(("Income by source", ["Source", "Transactions", "Total"],
                      [[s["name"], s["count"], s["total"]] for s in ctx["by_source"]]))
    if kind == "income":
        S.append(("Income records", ["Date", "Source", "Description", "Amount"],
                  [[i.date_received.strftime("%d %b %Y"), i.source.name, i.description, i.amount] for i in ctx["incomes"]]))
    if kind in ("expense", "daily"):
        S.append(("Expense records", ["Date", "Description", "Category", "Paid with", "Planned?", "Amount"],
                  [[e.expense_date.strftime("%d %b %Y"), e.description, e.category.name, e.get_payment_method_display(),
                    "Planned" if e.is_planned else "Unplanned", e.amount] for e in ctx["expenses"]]))
    if kind == "savings":
        S.append(("Goal progress", ["Goal", "Saved", "Target", "Remaining", "Progress"],
                  [[g.name, g.current_amount, g.target_amount, g.remaining, f"{g.progress}%"] for g in ctx["goals"]]))
        S.append(("Contributions in this period", ["Date", "Goal", "Amount"],
                  [[c.contribution_date.strftime("%d %b %Y"), c.goal.name, c.amount] for c in ctx["contributions"]]))
    return S


def period_text(ctx):
    s, e = ctx["start"], ctx["end"]
    return s.strftime("%d %B %Y") if s == e else f"{s:%d %B %Y} to {e:%d %B %Y}"
