from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Recommendation(models.Model):
    """A personalised, evidence-backed suggestion. One row per (student, key); the key identifies the rule
    and subject (e.g. 'category_rise:Entertainment') so the same advice is never created twice."""
    PENDING, ACCEPTED, DISMISSED, COMPLETED = "PENDING", "ACCEPTED", "DISMISSED", "COMPLETED"
    STATUS_CHOICES = [(PENDING, "Pending"), (ACCEPTED, "Accepted"), (DISMISSED, "Dismissed"), (COMPLETED, "Completed")]
    STATUSES = [s for s, _ in STATUS_CHOICES]
    HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"
    LEVEL_CHOICES = [(HIGH, "High"), (MEDIUM, "Medium"), (LOW, "Low")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations")
    key = models.CharField(max_length=100)
    title = models.CharField(max_length=140)
    observation = models.TextField()
    evidence = models.TextField()
    explanation = models.TextField()
    action = models.TextField()
    suggested_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                           validators=[MinValueValidator(Decimal("0.01"))])
    estimated_impact = models.CharField(max_length=255, blank=True)
    confidence = models.CharField(max_length=6, choices=LEVEL_CHOICES)
    confidence_note = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=6, choices=LEVEL_CHOICES)
    # for outcome tracking (only recommendations about one spending category)
    category = models.ForeignKey("core.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    baseline_monthly = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    is_active = models.BooleanField(default=True, help_text="False when a pending recommendation no longer applies.")
    useful = models.BooleanField(null=True, blank=True, help_text="Student feedback: was this recommendation useful?")
    generated_on = models.DateField()
    review_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-generated_on", "id"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="one_recommendation_per_key")]

    def __str__(self):
        return f"{self.title} ({self.status})"

    def set_status(self, new_status):
        now = timezone.now()
        if new_status == self.ACCEPTED and self.accepted_at is None:
            self.accepted_at = now
        if new_status == self.PENDING:
            self.accepted_at = None
        self.status = new_status
        self.status_changed_at = now
        self.save(update_fields=["status", "status_changed_at", "accepted_at"])

    @property
    def is_overdue_for_review(self):
        return self.status in (self.PENDING, self.ACCEPTED) and self.review_date < timezone.localdate()
