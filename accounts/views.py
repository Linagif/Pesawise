from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegisterForm, _split_name
from .models import Profile


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to PesaWise, {user.first_name}! Start by recording your income.")
        return redirect("dashboard:home")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    prof, _ = Profile.objects.get_or_create(user=request.user)
    initial = {"full_name": request.user.get_full_name(), "email": request.user.email,
               "daily_spending_target": prof.daily_spending_target}
    form = ProfileForm(request.POST or None, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        request.user.first_name, request.user.last_name = _split_name(form.cleaned_data["full_name"])
        request.user.email = form.cleaned_data["email"]
        request.user.save()
        prof.daily_spending_target = form.cleaned_data["daily_spending_target"]
        prof.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
