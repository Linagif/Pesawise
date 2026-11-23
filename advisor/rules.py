"""Rule-based financial advisor. No AI services: just transparent if/else rules over the student's own records.
Each rule only fires when there is enough data, so we never give misleading advice."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum

from budgets.models import Budget
from core.models import Category
from core.utils import money, month_range
from dashboard import services as svc
from expenses.models import Expense
from savings.models import SavingsGoal

MIN_DAYS_FOR_AVERAGE = 5
MIN_EXPENSES_FOR_HABITS = 3


def _tip(level, title, text):
    return {"level": level, "title": title, "text": text}


def generate_tips(user, today):
    tips = []
    start, end = month_range(today.year, today.month)
    total_exp = Expense.objects.filter(user=user).count()
    if total_exp == 0:
        return [_tip("info", "Get started", "Record your first expense and income so PesaWise can give you useful tips.")]

    # --- budget rules ---
    budget = Budget.objects.filter(user=user, month=today.month, year=today.year).first()
    if not budget or not budget.allocations.exists():
        tips.append(_tip("info", "Set a budget", "You have no budget for this month. A simple limit for food, transport "
                                                 "and entertainment makes it much easier to control spending."))
    else:
        prog = svc.budget_progress(budget)
        for row in prog["rows"]:
            if row["category"].category_type == Category.SAVINGS:
                continue
            pct = row["pct"]
            if row["allocated"] <= 0 and row["actual"] > 0:
                tips.append(_tip("danger", f"{row['name']}: no budget", f"You spent KSh {row['actual']:,.2f} on {row['name']} "
                                 "but gave it no limit this month. Consider setting one."))
            elif pct is not None and pct > 100:
                tips.append(_tip("danger", f"{row['name']}: over budget",
                                 f"You have gone over your {row['name']} budget by KSh {-row['remaining']:,.2f}. "
                                 "Try to avoid more spending here for the rest of the month."))
            elif pct is not None and pct >= 80:
                tips.append(_tip("warning", f"{row['name']}: nearly used up",
                                 f"You have used {pct}% of your {row['name']} budget. Consider reducing unnecessary "
                                 f"{row['name'].lower()} purchases for the rest of the month."))
            elif pct is not None and row["allocated"] > 0 and row["actual"] > 0 and today.day >= 20:
                tips.append(_tip("success", f"{row['name']}: on track",
                                 f"You have stayed within your {row['name'].lower()} budget so far this month. Keep it up!"))
        if prog["unbudgeted"] > 0:
            tips.append(_tip("info", "Spending without a budget line", f"KSh {prog['unbudgeted']:,.2f} was spent in "
                             "categories that have no limit in this month's budget."))

    # --- daily spending vs average ---
    today_total = svc.total_expenses(user, today, today)
    avg, days = svc.average_daily_spend_before(user, today)
    if today_total > 0 and days >= MIN_DAYS_FOR_AVERAGE and today_total > avg:
        tips.append(_tip("warning", "Higher than usual today",
                         f"You have spent KSh {today_total:,.2f} today, more than your average of KSh {avg:,.2f} per day this month."))
    prof = getattr(user, "profile", None)
    if prof and prof.daily_spending_target and today_total > prof.daily_spending_target:
        tips.append(_tip("warning", "Daily target passed", f"You are KSh {today_total - prof.daily_spending_target:,.2f} "
                         "above your daily spending target."))

    # --- unplanned purchases (last 7 days) ---
    week = Expense.objects.filter(user=user, expense_date__gt=today - timedelta(days=7), expense_date__lte=today)
    n_week, n_unplanned = week.count(), week.filter(is_planned=False).count()
    if n_week >= MIN_EXPENSES_FOR_HABITS and n_unplanned >= 3:
        tips.append(_tip("warning", "Several unplanned purchases",
                         f"You recorded {n_unplanned} unplanned purchases in the last 7 days. Consider reviewing your spending habits."))

    # --- savings goals ---
    for g in SavingsGoal.objects.filter(user=user):
        recent = g.contributions.filter(contribution_date__gte=start, contribution_date__lte=end).exists()
        if g.is_complete:
            tips.append(_tip("success", f"Goal reached: {g.name}", "Congratulations, you have reached this goal!"))
        elif recent:
            tips.append(_tip("success", f"Saving for {g.name}",
                             f"You are {g.progress}% of the way to your goal. Keep contributing regularly."))
        elif g.target_date >= today:
            tips.append(_tip("info", f"{g.name}: no savings this month", f"You have not added to this goal this month. "
                             f"KSh {g.remaining:,.2f} remains before {g.target_date:%d %b %Y}."))
        else:
            tips.append(_tip("warning", f"{g.name}: past target date", f"The target date has passed with KSh "
                             f"{g.remaining:,.2f} still to save. Consider updating the date or increasing contributions."))

    # --- overall balance ---
    if svc.available_balance(user) < 0:
        tips.append(_tip("danger", "Negative balance", "You have recorded more spending and savings than income. "
                         "Check that all the money you received has been entered."))

    order = {"danger": 0, "warning": 1, "info": 2, "success": 3}
    tips.sort(key=lambda t: order[t["level"]])
    if not tips:
        tips.append(_tip("info", "Looking good", "Nothing to flag right now. Keep recording your spending."))
    return tips
