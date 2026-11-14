from datetime import timedelta

from django import forms
from django.utils import timezone

from core.forms import DATE_WIDGET, UserModelForm

from .models import SavingsContribution, SavingsGoal


class GoalForm(UserModelForm):
    class Meta:
        model = SavingsGoal
        fields = ["name", "target_amount", "starting_amount", "target_date", "description"]
        widgets = {"target_date": DATE_WIDGET(), "description": forms.Textarea(attrs={"rows": 2})}
        labels = {"starting_amount": "Already saved (KSh)", "target_amount": "Target amount (KSh)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("target_amount", "starting_amount"):
            self.fields[f].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["name"].widget.attrs["placeholder"] = "e.g. Laptop, Emergency fund, School fees"
        if not self.instance.pk:
            self.fields["target_date"].initial = timezone.localdate() + timedelta(days=90)

    def clean_target_date(self):
        date = self.cleaned_data["target_date"]
        if not self.instance.pk and date < timezone.localdate():
            raise forms.ValidationError("Choose a target date that is today or later.")
        return date


class ContributionForm(UserModelForm):
    class Meta:
        model = SavingsContribution
        fields = ["amount", "contribution_date", "notes"]
        widgets = {"contribution_date": DATE_WIDGET(), "notes": forms.Textarea(attrs={"rows": 2})}
        labels = {"amount": "Amount saved (KSh)", "contribution_date": "Date"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0.01", "inputmode": "decimal"})
        self.fields["contribution_date"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not self.instance.pk:
            self.fields["contribution_date"].initial = timezone.localdate()
