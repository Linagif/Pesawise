from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum

from core.models import Category
from core.utils import money
from core.validators import non_negative_amount


class Budget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [models.UniqueConstraint(fields=["user", "month", "year"], name="one_budget_per_month")]

    def __str__(self):
        return f"Budget {self.month}/{self.year}"

    @property
    def label(self):
        import calendar
        return f"{calendar.month_name[self.month]} {self.year}"

    @property
    def total_amount(self):
        """Total budget is always calculated from the allocations (never stored, so it cannot go stale)."""
        return money(self.allocations.aggregate(t=Sum("allocated_amount"))["t"])


class BudgetAllocation(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="allocations")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="allocations")
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[non_negative_amount])

    class Meta:
        ordering = ["category__name"]
        constraints = [models.UniqueConstraint(fields=["budget", "category"], name="one_allocation_per_category")]

    def __str__(self):
        return f"{self.category}: {self.allocated_amount}"

    def clean(self):
        if self.category_id:
            if self.category.category_type == Category.INCOME:
                raise ValidationError({"category": "Income sources cannot be budgeted."})
            if self.budget_id and self.category.user_id not in (None, self.budget.user_id):
                raise ValidationError({"category": "Choose a valid category."})
