from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from core.utils import money
from core.validators import non_negative_amount, not_in_future, positive_amount


class SavingsGoal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="savings_goals")
    name = models.CharField(max_length=100, verbose_name="Goal name")
    target_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[positive_amount])
    starting_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[non_negative_amount],
        help_text="Money you had already saved for this goal BEFORE using PesaWise. "
                  "It does not change your available balance.")
    target_date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target_date", "name"]

    def __str__(self):
        return self.name

    # Everything below is calculated from contributions so edits/deletes can never leave it out of sync.
    @property
    def contributed_total(self):
        return money(self.contributions.aggregate(t=Sum("amount"))["t"])

    @property
    def current_amount(self):
        return money(self.starting_amount + self.contributed_total)

    @property
    def remaining(self):
        return max(Decimal("0.00"), money(self.target_amount - self.current_amount))

    @property
    def progress(self):
        pct = (self.current_amount / self.target_amount * 100) if self.target_amount else Decimal(0)
        return min(Decimal("100.0"), pct.quantize(Decimal("0.1")))

    @property
    def is_complete(self):
        return self.current_amount >= self.target_amount


class SavingsContribution(models.Model):
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name="contributions")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[positive_amount])
    contribution_date = models.DateField(validators=[not_in_future])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-contribution_date", "-id"]

    def __str__(self):
        return f"{self.amount} to {self.goal}"
