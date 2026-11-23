import calendar

from django import forms
from django.utils import timezone

from core.forms import UserModelForm, style_fields
from core.models import Category
from core.validators import non_negative_amount

from .models import Budget, BudgetAllocation


class BudgetForm(forms.Form):
    month = forms.TypedChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)], coerce=int)
    year = forms.IntegerField(min_value=2000, max_value=2100)
    copy_previous = forms.BooleanField(required=False, initial=True,
                                       label="Start from my most recent budget's category limits")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["month"].initial = today.month
        self.fields["year"].initial = today.year
        style_fields(self)

    def clean(self):
        cleaned = super().clean()
        month, year = cleaned.get("month"), cleaned.get("year")
        if month and year and Budget.objects.filter(user=self.user, month=month, year=year).exists():
            raise forms.ValidationError(
                f"You already have a budget for {calendar.month_name[month]} {year}. Open it to edit it.")
        return cleaned


class AllocationForm(UserModelForm):
    class Meta:
        model = BudgetAllocation
        fields = ["category", "allocated_amount"]
        labels = {"allocated_amount": "Spending limit (KSh)"}

    def __init__(self, *args, budget=None, **kwargs):
        super().__init__(*args, **kwargs)
        used = budget.allocations.values_list("category_id", flat=True) if budget else []
        self.fields["category"].queryset = (Category.objects.visible_to(self.user)
                                            .of_type(Category.EXPENSE, Category.SAVINGS).exclude(pk__in=used))
        self.fields["allocated_amount"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})


class AllocationEditForm(UserModelForm):
    class Meta:
        model = BudgetAllocation
        fields = ["allocated_amount"]
        labels = {"allocated_amount": "Spending limit (KSh)"}
