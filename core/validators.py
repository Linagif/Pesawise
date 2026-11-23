from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

positive_amount = MinValueValidator(Decimal("0.01"), message="Amount must be greater than zero.")
non_negative_amount = MinValueValidator(Decimal("0.00"), message="Amount cannot be negative.")


def not_in_future(value):
    if value > timezone.localdate():
        raise ValidationError("The date cannot be in the future.")
