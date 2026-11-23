from django import forms

from .models import Category


def style_fields(form):
    """Apply Bootstrap 5 classes to every widget of a form."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.RadioSelect):
            cls = "form-check-input"
        elif isinstance(widget, forms.CheckboxInput):
            cls = "form-check-input"
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            cls = "form-select"
        else:
            cls = "form-control"
        widget.attrs["class"] = f"{widget.attrs.get('class', '')} {cls}".strip()


DATE_WIDGET = lambda: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})  # noqa: E731


class UserModelForm(forms.ModelForm):
    """ModelForm that knows the logged-in user and styles itself."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_fields(self)


class CategoryForm(UserModelForm):
    class Meta:
        model = Category
        fields = ["name", "category_type", "spending_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_type"].choices = [(Category.EXPENSE, "Expense category"),
                                                (Category.INCOME, "Income source")]
        self.fields["category_type"].label = "Type"
        self.fields["spending_type"].required = False          # omitted -> model default (discretionary)
        self.fields["spending_type"].label = "Kind of spending"
        self.fields["spending_type"].help_text = ("Needs (rent, food, transport...) or wants. "
                                                  "Used by the Financial Health page. Ignored for income sources.")
