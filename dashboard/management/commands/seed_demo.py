"""python manage.py seed_demo  ->  creates a demo student (demo / demo12345) with realistic KES data."""
from datetime import timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from budgets.models import Budget, BudgetAllocation
from core.models import Category
from expenses.models import Expense
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal


class Command(BaseCommand):
    help = "Create a demo student account with sample data (for demonstration only)."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username="demo", defaults={
            "first_name": "Amina", "last_name": "Wanjiru", "email": "demo@example.com"})
        if not created:
            self.stdout.write("Demo user already exists. Delete it first to re-seed.")
            return
        user.set_password("demo12345")
        user.save()
        user.profile.daily_spending_target = D("400")
        user.profile.save()
        today = timezone.localdate()
        cat = lambda n, t: Category.objects.get(user__isnull=True, name=n, category_type=t)  # noqa: E731
        Income.objects.create(user=user, source=cat("Parents or guardians", "INCOME"), amount=D("10000"),
                              date_received=today.replace(day=1), description="Monthly upkeep")
        Income.objects.create(user=user, source=cat("Casual jobs", "INCOME"), amount=D("2500"),
                              date_received=today - timedelta(days=4), description="Weekend event work")
        b = Budget.objects.create(user=user, month=today.month, year=today.year)
        for name, amt in [("Rent", 3000), ("Food", 2500), ("Transport", 1500), ("Internet and airtime", 500),
                          ("Entertainment", 500), ("Miscellaneous", 1000)]:
            BudgetAllocation.objects.create(budget=b, category=cat(name, "EXPENSE"), allocated_amount=D(amt))
        BudgetAllocation.objects.create(budget=b, category=cat("Savings", "SAVINGS"), allocated_amount=D("1000"))
        rows = [("Lunch", "Food", 200, True), ("Matatu fare", "Transport", 100, True), ("Airtime", "Internet and airtime", 50, True),
                ("Snacks", "Food", 100, False), ("Printing notes", "Education and academic materials", 50, True),
                ("Movie night", "Entertainment", 350, False), ("Groceries", "Food", 650, True), ("Rent", "Rent", 3000, True)]
        for i, (desc, c, amt, planned) in enumerate(rows):
            d = max(today.replace(day=1), today - timedelta(days=i))
            Expense.objects.create(user=user, category=cat(c, "EXPENSE"), amount=D(amt), description=desc,
                                   expense_date=d, payment_method="MPESA", is_planned=planned)
        g = SavingsGoal.objects.create(user=user, name="Laptop", target_amount=D("10000"), starting_amount=D("3000"),
                                       target_date=today + timedelta(days=120), description="For coding assignments")
        SavingsContribution.objects.create(goal=g, amount=D("1000"), contribution_date=today - timedelta(days=2))
        self.stdout.write(self.style.SUCCESS("Demo created. Log in with  demo / demo12345"))
