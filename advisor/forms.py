"""Forms for the what-if simulator. All use GET (read-only, bookmarkable), validated before any maths runs."""
from decimal import Decimal

from django import forms

from core.forms import style_fields
from core.models import Category

MAX_AMOUNT = Decimal("100000000")


def _money_field(label, required=True, help_text=""):
    return forms.DecimalField(label=label, required=required, min_value=Decimal("0.01"), max_value=MAX_AMOUNT,
                              max_digits=12, decimal_places=2, help_text=help_text,
                              widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}))


class _Base(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.setup()
        style_fields(self)

    def setup(self):
        pass


class AffordForm(_Base):
    price = _money_field("Price of the item (KSh)")
    months = forms.IntegerField(label="Months until you want to buy it (optional)", required=False, min_value=1, max_value=120,
                                help_text="Leave empty to see whether you can pay now, or how long it would take.")


class SaveForm(_Base):
    monthly = _money_field("Amount to save each month (KSh)", required=False)
    target = _money_field("Savings target (KSh)", required=False)

    def clean(self):
        cleaned = super().clean()
        if not self.errors and cleaned.get("monthly") is None and cleaned.get("target") is None:
            raise forms.ValidationError("Enter a monthly amount, a target, or both.")
        return cleaned


class CutForm(_Base):
    category = forms.ModelChoiceField(queryset=Category.objects.none(), label="Category", empty_label="Choose a category")
    reduction = _money_field("Reduce it by, per month (KSh)")

    def setup(self):
        self.fields["category"].queryset = Category.objects.visible_to(self.user).of_type(Category.EXPENSE)


class IncomeChangeForm(_Base):
    direction = forms.ChoiceField(choices=[("decrease", "Decreases"), ("increase", "Increases")], label="My income")
    mode = forms.ChoiceField(choices=[("percent", "by a percentage (%)"), ("amount", "by an amount (KSh)")], label="Measured")
    value = forms.DecimalField(label="How much", min_value=Decimal("0.01"), max_value=MAX_AMOUNT, max_digits=12, decimal_places=2,
                               widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}))

    def clean(self):
        cleaned = super().clean()
        if not self.errors and cleaned["direction"] == "decrease" and cleaned["mode"] == "percent" and cleaned["value"] > 100:
            raise forms.ValidationError("Income cannot fall by more than 100%.")
        return cleaned
