"""Shared helpers for the test suite."""
from datetime import timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget, BudgetAllocation
from core.models import Category
from expenses.models import Expense
from income.models import Income
from savings.models import SavingsContribution, SavingsGoal

User = get_user_model()


def cat(name, ctype=Category.EXPENSE):
    return Category.objects.get(user__isnull=True, name=name, category_type=ctype)


class BaseTestCase(TestCase):
    """Two students, so every test can also check data isolation."""
    PASSWORD = "S3cure-pass-987"

    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user("alice", "alice@example.com", self.PASSWORD, first_name="Alice")
        self.other = User.objects.create_user("bob", "bob@example.com", self.PASSWORD, first_name="Bob")
        self.client.login(username="alice", password=self.PASSWORD)

    # factories
    def income(self, amount, user=None, source="Parents or guardians", day=None, desc="Upkeep"):
        return Income.objects.create(user=user or self.user, source=cat(source, Category.INCOME), amount=D(str(amount)),
                                     date_received=day or self.today, description=desc)

    def expense(self, amount, user=None, category="Food", day=None, desc="Lunch", planned=True):
        return Expense.objects.create(user=user or self.user, category=cat(category), amount=D(str(amount)),
                                      expense_date=day or self.today, description=desc, is_planned=planned)

    def budget(self, user=None, **limits):
        b = Budget.objects.create(user=user or self.user, month=self.today.month, year=self.today.year)
        for name, amount in limits.items():
            ctype = Category.SAVINGS if name == "Savings" else Category.EXPENSE
            BudgetAllocation.objects.create(budget=b, category=cat(name.replace("_", " "), ctype), allocated_amount=D(str(amount)))
        return b

    def goal(self, target=10000, start=0, user=None, name="Laptop"):
        return SavingsGoal.objects.create(user=user or self.user, name=name, target_amount=D(str(target)),
                                          starting_amount=D(str(start)), target_date=self.today + timedelta(days=60))

    def contribute(self, goal, amount, day=None):
        return SavingsContribution.objects.create(goal=goal, amount=D(str(amount)), contribution_date=day or self.today)
