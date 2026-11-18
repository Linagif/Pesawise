from django import forms

from core.forms import style_fields

from .parser import MAX_CHARS


class PasteForm(forms.Form):
    text = forms.CharField(
        label="Paste your M-Pesa confirmation messages", max_length=MAX_CHARS,
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "Paste one or many messages here...", "autocomplete": "off"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
