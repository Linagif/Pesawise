from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from core.forms import style_fields
from core.validators import positive_amount

User = get_user_model()


def _split_name(full_name):
    parts = full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


class RegisterForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("full_name", "username", "email")

    field_order = ["full_name", "email", "username", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name, user.last_name = _split_name(self.cleaned_data["full_name"])
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    daily_spending_target = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, validators=[positive_amount],
        label="Daily spending target (KSh)", help_text="Optional. Used for 'remaining today' on your dashboard.")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email


from django.contrib.auth import forms as auth_forms  # noqa: E402


class _Styled:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class StyledAuthForm(_Styled, auth_forms.AuthenticationForm):
    pass


class StyledPasswordResetForm(_Styled, auth_forms.PasswordResetForm):
    pass


class StyledSetPasswordForm(_Styled, auth_forms.SetPasswordForm):
    pass


class StyledPasswordChangeForm(_Styled, auth_forms.PasswordChangeForm):
    pass
