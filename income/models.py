from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import Category
from core.validators import not_in_future, positive_amount


class Income(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incomes")
    source = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="incomes")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[positive_amount])
    date_received = models.DateField(validators=[not_in_future])
    description = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_received", "-id"]

    def __str__(self):
        return f"{self.source} {self.amount} on {self.date_received}"

    def clean(self):
        if self.source_id:
            if self.source.category_type != Category.INCOME:
                raise ValidationError({"source": "Choose a valid income source."})
            if self.user_id and self.source.user_id not in (None, self.user_id):
                raise ValidationError({"source": "Choose a valid income source."})
