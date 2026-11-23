from datetime import timedelta

from django import forms
from django.utils import timezone

from core.forms import DATE_WIDGET, UserModelForm, style_fields
from core.models import Category

from .models import Expense

PLANNED_CHOICES = [("True", "Planned"), ("False", "Unplanned")]


class ExpenseForm(UserModelForm):
    is_planned = forms.TypedChoiceField(
        choices=PLANNED_CHOICES, coerce=lambda v: v == "True", widget=forms.RadioSelect,
        initial="True", label="Was it planned?")

    class Meta:
        model = Expense
        fields = ["amount", "description", "category", "expense_date", "payment_method", "is_planned", "notes"]
        widgets = {"expense_date": DATE_WIDGET(), "notes": forms.Textarea(attrs={"rows": 2})}
        labels = {"expense_date": "Date", "amount": "Amount spent (KSh)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.visible_to(self.user).of_type(Category.EXPENSE)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0.01", "inputmode": "decimal"})
        self.fields["expense_date"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["description"].widget.attrs["placeholder"] = "e.g. Lunch at the canteen"
        self.fields["notes"].required = False
        if self.instance.pk:
            self.initial["is_planned"] = str(self.instance.is_planned)
        else:
            self.fields["expense_date"].initial = timezone.localdate()
            # smart defaults: reuse the last category and payment method
            last = Expense.objects.filter(user=self.user).first() if self.user else None
            if last:
                self.fields["category"].initial = last.category_id
                self.fields["payment_method"].initial = last.payment_method

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and self.user and not self.errors:
            recent = Expense.objects.filter(
                user=self.user, amount=cleaned.get("amount"), description=cleaned.get("description"),
                category=cleaned.get("category"), expense_date=cleaned.get("expense_date"),
                created_at__gte=timezone.now() - timedelta(seconds=10))
            if recent.exists():
                raise forms.ValidationError(
                    "This looks like a duplicate of an expense you just saved. "
                    "If you really spent it twice, wait a few seconds and save again.")
        return cleaned


class ExpenseFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Search description"}))
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False, empty_label="All categories")
    payment_method = forms.ChoiceField(choices=[("", "Any payment method")] + Expense.PAYMENT_CHOICES, required=False)
    planned = forms.ChoiceField(choices=[("", "Planned & unplanned"), ("1", "Planned only"), ("0", "Unplanned only")],
                                required=False)
    start = forms.DateField(required=False, label="From", widget=DATE_WIDGET())
    end = forms.DateField(required=False, label="To", widget=DATE_WIDGET())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.visible_to(user).of_type(Category.EXPENSE)
        style_fields(self)
