from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.validators import non_negative_amount, positive_amount

from . import parser as p


class ImportedTransaction(models.Model):
    """One parsed mobile-money message waiting for the student's decision (or already decided).
    Stores only the minimum: no phone numbers, no balance, no original message text."""
    MPESA = "MPESA"
    PENDING, IMPORTED, SKIPPED = "PENDING", "IMPORTED", "SKIPPED"
    STATUS_CHOICES = [(PENDING, "Waiting for review"), (IMPORTED, "Saved"), (SKIPPED, "Skipped")]
    KIND_CHOICES = [(p.SENT, "Sent to a person"), (p.PAID, "Paid to a till"), (p.PAYBILL, "Paybill payment"),
                    (p.RECEIVED, "Money received"), (p.WITHDRAW, "Cash withdrawal"), (p.DEPOSIT, "Cash deposit"),
                    (p.AIRTIME, "Airtime purchase"), (p.REVERSAL, "Reversal")]
    EXPENSE_KINDS = {p.SENT, p.PAID, p.PAYBILL, p.AIRTIME}
    INCOME_KINDS = {p.RECEIVED, p.REVERSAL}
    CASH_KINDS = {p.WITHDRAW, p.DEPOSIT}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="imported_transactions")
    provider = models.CharField(max_length=10, default=MPESA)
    reference = models.CharField(max_length=20)                      # the M-Pesa transaction code
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[positive_amount])
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[non_negative_amount])
    counterparty = models.CharField(max_length=120, blank=True)
    occurred_on = models.DateField()
    occurred_time = models.TimeField(null=True, blank=True)
    reversal_of = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    expense = models.ForeignKey("expenses.Expense", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    charge_expense = models.ForeignKey("expenses.Expense", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    income = models.ForeignKey("income.Income", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_on", "-occurred_time", "id"]
        constraints = [models.UniqueConstraint(fields=["user", "provider", "reference"], name="one_import_per_reference")]

    def __str__(self):
        return f"{self.reference} {self.kind} {self.amount}"

    @property
    def group(self):
        if self.kind in self.EXPENSE_KINDS:
            return "expense"
        if self.kind in self.INCOME_KINDS:
            return "income"
        return "cash"

    @property
    def description(self):
        who = self.counterparty
        return {p.SENT: f"Sent to {who}", p.PAID: f"Paid to {who}", p.PAYBILL: f"Paybill: {who}", p.AIRTIME: "Airtime",
                p.RECEIVED: f"Received from {who}", p.WITHDRAW: f"Cash withdrawal ({who})" if who else "Cash withdrawal",
                p.DEPOSIT: f"Cash deposit ({who})" if who else "Cash deposit",
                p.REVERSAL: f"Reversal of {self.reversal_of}"}[self.kind]
