from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from advisor.rules import generate_tips
from budgets.models import Budget
from core.utils import ZERO, money, month_range, week_range
from expenses.models import Expense
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal

from . import services as svc
from .exports import report_csv_response, report_pdf_response
from .reports import build_report


def _recent_transactions(user, limit=10):
    rows = []
    for i in Income.objects.filter(user=user).select_related("source")[:limit]:
        rows.append({"kind": "income", "date": i.date_received, "created": i.created_at, "description": i.description,
                     "category": i.source.name, "amount": i.amount, "id": i.pk})
    for e in Expense.objects.filter(user=user).select_related("category")[:limit]:
        rows.append({"kind": "expense", "date": e.expense_date, "created": e.created_at, "description": e.description,
                     "category": e.category.name, "amount": e.amount, "id": e.pk})
    for c in SavingsContribution.objects.filter(goal__user=user).select_related("goal")[:limit]:
        rows.append({"kind": "saving", "date": c.contribution_date, "created": c.created_at,
                     "description": f"Saved for {c.goal.name}", "category": "Savings", "amount": c.amount, "id": c.pk})
    rows.sort(key=lambda r: (r["date"], r["created"]), reverse=True)
    return rows[:limit]


@login_required
def home(request):
    user, today = request.user, timezone.localdate()
    start, end = month_range(today.year, today.month)
    budget = Budget.objects.filter(user=user, month=today.month, year=today.year).first()
    prog = svc.budget_progress(budget) if budget else None
    goals = list(SavingsGoal.objects.filter(user=user))
    daily = svc.daily_summary(user, today)
    month_cats = svc.spending_by_category(user, start, end)
    series = svc.monthly_series(user, today, 6)
    trend = svc.daily_series(user, start, today)
    cards = {
        "income": svc.total_income(user), "expenses": svc.total_expenses(user),
        "balance": svc.available_balance(user), "savings": svc.total_savings(user),
        "budget": prog["total_allocated"] if prog else None,
        "budget_remaining": prog["remaining"] if prog else None,
    }
    chart = {
        "months": [m["label"] for m in series],
        "income": [float(m["income"]) for m in series], "expenses": [float(m["expenses"]) for m in series],
        "cat_labels": [c["name"] for c in month_cats], "cat_values": [float(c["total"]) for c in month_cats],
        "trend_labels": [d["date"].strftime("%d %b") for d in trend], "trend_values": [float(d["total"]) for d in trend],
        "budget_labels": [r["name"] for r in prog["rows"]] if prog else [],
        "budget_alloc": [float(r["allocated"]) for r in prog["rows"]] if prog else [],
        "budget_actual": [float(r["actual"]) for r in prog["rows"]] if prog else [],
        "goal_labels": [g.name for g in goals], "goal_progress": [float(g.progress) for g in goals],
    }
    return render(request, "dashboard/home.html", {
        "today": today, "cards": cards, "daily": daily, "budget": budget, "prog": prog, "goals": goals,
        "recent": _recent_transactions(user), "tips": generate_tips(user, today)[:4], "chart": chart,
        "has_data": bool(cards["income"] or cards["expenses"])})


@login_required
def reports(request):
    return render(request, "dashboard/report.html", build_report(request.user, request.GET))


@login_required
def report_export_csv(request):
    return report_csv_response(build_report(request.user, request.GET), request.user)


@login_required
def report_export_pdf(request):
    return report_pdf_response(build_report(request.user, request.GET), request.user)
