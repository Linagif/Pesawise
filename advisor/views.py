from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .rules import generate_tips


@login_required
def tips(request):
    return render(request, "advisor/tips.html", {"tips": generate_tips(request.user, timezone.localdate())})
