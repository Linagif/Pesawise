from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import Category
from core.validators import not_in_future, positive_amount


class Expense(models.Model):
    CASH, MPESA, BANK, CARD, OTHER = "CASH", "MPESA", "BANK", "CARD", "OTHER"
    PAYMENT_CHOICES = [(CASH, "Cash"), (MPESA, "M-Pesa"), (BANK, "Bank"), (CARD, "Card"), (OTHER, "Other")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[positive_amount])
    description = models.CharField(max_length=200)
    expense_date = models.DateField(validators=[not_in_future])
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=MPESA)
    is_planned = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]
        indexes = [models.Index(fields=["user", "expense_date"])]

    def __str__(self):
        return f"{self.description} ({self.amount})"

    def clean(self):
        if self.category_id:
            if self.category.category_type != Category.EXPENSE:
                raise ValidationError({"category": "Choose a valid expense category."})
            if self.user_id and self.category.user_id not in (None, self.user_id):
                raise ValidationError({"category": "Choose a valid expense category."})
