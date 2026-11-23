from django.conf import settings
from django.db import models

from core.validators import positive_amount


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    daily_spending_target = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[positive_amount],
        help_text="Optional. The most you want to spend in one day (KSh).")

    is_demo = models.BooleanField(default=False, help_text="Disposable sandbox account created by 'Try the demo'.")

    def __str__(self):
        return f"Profile of {self.user}"
