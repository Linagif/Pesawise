from django import forms
from django.utils import timezone

from core.forms import DATE_WIDGET, UserModelForm, style_fields
from core.models import Category

from .models import Income


class IncomeForm(UserModelForm):
    class Meta:
        model = Income
        fields = ["source", "amount", "date_received", "description", "notes"]
        widgets = {"date_received": DATE_WIDGET(), "notes": forms.Textarea(attrs={"rows": 2})}
        labels = {"source": "Income source", "date_received": "Date received"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = Category.objects.visible_to(self.user).of_type(Category.INCOME)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0.01", "inputmode": "decimal"})
        self.fields["date_received"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not self.instance.pk:
            self.fields["date_received"].initial = timezone.localdate()


class IncomeFilterForm(forms.Form):
    source = forms.ModelChoiceField(queryset=Category.objects.none(), required=False, empty_label="All sources")
    start = forms.DateField(required=False, label="From", widget=DATE_WIDGET())
    end = forms.DateField(required=False, label="To", widget=DATE_WIDGET())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = Category.objects.visible_to(user).of_type(Category.INCOME)
        style_fields(self)
