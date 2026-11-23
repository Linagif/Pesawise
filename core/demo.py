"""Demo mode: realistic FAKE data, and disposable per-visitor accounts for a public portfolio site.

Design
  * Every visitor who presses 'Try the demo' gets their OWN account ('demo-<random>') with its own fake data, so one
    visitor can never see or change another's. The account has no usable password and cannot be logged into any other way.
  * Demo accounts and all their data are deleted after DEMO_LIFETIME_HOURS, and the number of live demos is capped.
  * Demo mode is OFF unless DJANGO_DEMO_ENABLED is set (or DEBUG is on), so a production deployment never exposes it by accident.
"""
import os
import secrets
from datetime import date, timedelta
from decimal import Decimal as D

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from budgets.models import Budget, BudgetAllocation
from core.models import Category
from core.utils import add_months, month_range
from expenses.models import Expense
from imports import services as import_services
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal

DEMO_LIFETIME_HOURS = 24
MAX_ACTIVE_DEMOS = 300
SESSION_SECONDS = 2 * 60 * 60


def demo_enabled():
    flag = os.environ.get("DJANGO_DEMO_ENABLED", "").lower() in ("1", "true", "yes", "on")
    return bool(flag or settings.DEBUG)


# ------------------------------------------------------------------ fake data
def populate_demo(user, today=None):
    """Fill an account with ~4 months of invented KES data that exercises every feature."""
    today = today or timezone.localdate()
    cat = lambda name, kind="EXPENSE": Category.objects.get(user__isnull=True, name=name, category_type=kind)  # noqa: E731

    def on(back, d):
        y, m = add_months(today.year, today.month, -back)
        return min(date(y, m, min(d, month_range(y, m)[1].day)), today)

    def spend(back, d, category, amount, desc, planned=True, method="MPESA"):
        when = on(back, d)
        if back == 0 and d > today.day:
            return                                          # never create future dates
        Expense.objects.create(user=user, category=cat(category), amount=D(str(amount)), description=desc,
                               expense_date=when, payment_method=method, is_planned=planned)

    for back in (3, 2, 1, 0):
        Income.objects.create(user=user, source=cat("Parents or guardians", "INCOME"), amount=D("10000"),
                              date_received=on(back, 1), description="Monthly upkeep")
        casual = {3: 2000, 2: 2500, 1: 3500, 0: 2500}[back]
        Income.objects.create(user=user, source=cat("Casual jobs", "INCOME"), amount=D(casual),
                              date_received=on(back, 15 if back else 3), description="Weekend event work")
        spend(back, 2, "Rent", 3000, "Rent")
        food = {3: 2200, 2: 2400, 1: 3600, 0: 1500}[back]
        weeks = (5, 12, 19, 26) if back else (3, 8)
        for d in weeks:
            spend(back, d, "Food", food / len(weeks), "Groceries")
        for d in (4, 9, 14, 19, 24, 28) if back else (4, 9):
            spend(back, d, "Transport", 200, "Matatu fare")
        spend(back, 8, "Entertainment", 600, "Showmax", method="CARD")                       # recurring
        outing = {2: 100, 1: 900, 0: 400}.get(back)
        if outing:
            spend(back, 22, "Entertainment", outing, "Outing with friends", planned=False)
        for d in (6, 13, 20, 27):
            spend(back, d, "Internet and airtime", 100, "Airtime")
        spend(back, 16, "Personal care", 350, "Haircut")
    # many small purchases in the last 3 weeks
    for i, (amt, what) in enumerate([(50, "Mandazi"), (70, "Tea and snack"), (60, "Chapati"), (90, "Juice"), (50, "Mandazi"),
                                     (80, "Samosas"), (60, "Tea"), (70, "Snack"), (50, "Mandazi"), (90, "Juice"), (60, "Chapati")]):
        when = today - timedelta(days=i + 1)
        Expense.objects.create(user=user, category=cat("Food"), amount=D(amt), description=what, expense_date=when,
                               payment_method="MPESA", is_planned=False)

    laptop = SavingsGoal.objects.create(user=user, name="Laptop", target_amount=D("40000"), starting_amount=D("3000"),
                                        target_date=today + timedelta(days=150), description="For coding assignments")
    for back, amt in ((3, 500), (2, 500), (1, 1000)):
        SavingsContribution.objects.create(goal=laptop, amount=D(amt), contribution_date=on(back, 20))
    fund = SavingsGoal.objects.create(user=user, name="Emergency fund", target_amount=D("15000"), starting_amount=D("0"),
                                      target_date=today + timedelta(days=240))
    SavingsContribution.objects.create(goal=fund, amount=D("500"), contribution_date=on(1, 25))
    SavingsContribution.objects.create(goal=fund, amount=D("500"), contribution_date=on(0, 3))

    limits = [("Rent", 3000), ("Food", 3000), ("Transport", 1500), ("Internet and airtime", 500), ("Entertainment", 1000),
              ("Personal care", 400)]
    for back in (1, 0):
        y, m = add_months(today.year, today.month, -back)
        b = Budget.objects.create(user=user, month=m, year=y)
        for name, amt in limits:
            BudgetAllocation.objects.create(budget=b, category=cat(name), allocated_amount=D(amt))
        BudgetAllocation.objects.create(budget=b, category=cat("Savings", "SAVINGS"), allocated_amount=D(1000))

    user.profile.daily_spending_target = D("400")
    user.profile.save()

    # three invented M-Pesa messages waiting in the review queue
    yesterday = today - timedelta(days=1)
    ref = lambda: ("D" + secrets.token_hex(5).upper())[:10]  # noqa: E731
    stamp = f"on {yesterday:%d/%m/%y} at 2:15 PM"
    messages = [f"{ref()} Confirmed. Ksh850.00 sent to JOHN KAMAU 0712345678 {stamp}. New M-PESA balance is Ksh1,234.56. Transaction cost, Ksh7.00.",
                f"{ref()} Confirmed. Ksh350.00 paid to FRESHMART SUPERMARKET. {stamp}.New M-PESA balance is Ksh884.56. Transaction cost, Ksh0.00.",
                f"{ref()} confirmed. You bought Ksh50.00 of airtime {stamp}.New M-PESA balance is Ksh834.56. Transaction cost, Ksh0.00."]
    import_services.import_text(user, "\n\n".join(messages), today)


# ------------------------------------------------------------------ visitor sandboxes
def purge_expired_demo(now=None):
    """Delete demo accounts older than the lifetime (cascades to all their data). Returns how many were removed."""
    now = now or timezone.now()
    User = get_user_model()
    old = User.objects.filter(profile__is_demo=True, date_joined__lt=now - timedelta(hours=DEMO_LIFETIME_HOURS))
    count = old.count()
    old.delete()
    return count


def active_demo_count():
    return get_user_model().objects.filter(profile__is_demo=True).count()


def create_visitor_demo():
    """Create a fresh sandbox user with fake data. Returns None if the demo is at capacity."""
    purge_expired_demo()
    if active_demo_count() >= MAX_ACTIVE_DEMOS:
        return None
    User = get_user_model()
    user = User.objects.create_user(username=f"demo-{secrets.token_hex(6)}", password=None, first_name="Demo",
                                    last_name="Student")                     # password=None -> unusable password
    user.profile.is_demo = True
    user.profile.save()
    populate_demo(user)
    return user
