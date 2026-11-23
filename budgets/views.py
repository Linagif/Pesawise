from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.templatetags.money import kes
from core.utils import add_months
from dashboard import services

from .forms import AllocationEditForm, AllocationForm, BudgetForm
from .models import Budget, BudgetAllocation


@login_required
def budget_list(request):
    rows = []
    for b in Budget.objects.filter(user=request.user):
        prog = services.budget_progress(b)
        rows.append({"budget": b, **prog})
    return render(request, "budgets/list.html", {"rows": rows})


@login_required
def budget_create(request):
    form = BudgetForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        month, year = form.cleaned_data["month"], form.cleaned_data["year"]
        try:
            budget = Budget.objects.create(user=request.user, month=month, year=year)
        except IntegrityError:   # double-click / race condition
            messages.error(request, "That month's budget already exists.")
            return redirect("budgets:list")
        copied = 0
        if form.cleaned_data["copy_previous"]:
            prev = (Budget.objects.filter(user=request.user).exclude(pk=budget.pk)
                    .filter(year__lte=year).order_by("-year", "-month"))
            prev = [b for b in prev if (b.year, b.month) < (year, month)]
            if prev:
                for a in prev[0].allocations.all():
                    BudgetAllocation.objects.create(budget=budget, category=a.category,
                                                    allocated_amount=a.allocated_amount)
                    copied += 1
        messages.success(request, f"Budget for {budget.label} created"
                                  + (f" with {copied} categories copied." if copied else ". Now add your category limits."))
        return redirect("budgets:detail", pk=budget.pk)
    return render(request, "form_page.html", {
        "title": "Create monthly budget", "form": form, "submit_label": "Create budget", "cancel_url": "budgets:list",
        "note": "Only one budget is allowed per month."})


@login_required
def budget_detail(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    form = AllocationForm(request.POST or None, user=request.user, budget=budget,
                          instance=BudgetAllocation(budget=budget))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{form.instance.category} limit set to {kes(form.instance.allocated_amount)}.")
        return redirect("budgets:detail", pk=budget.pk)
    return render(request, "budgets/detail.html", {
        "budget": budget, "form": form, **services.budget_progress(budget)})


@login_required
def allocation_edit(request, pk):
    alloc = get_object_or_404(BudgetAllocation, pk=pk, budget__user=request.user)
    form = AllocationEditForm(request.POST or None, user=request.user, instance=alloc)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Spending limit updated.")
        return redirect("budgets:detail", pk=alloc.budget_id)
    return render(request, "form_page.html", {
        "title": f"Edit limit: {alloc.category}", "form": form, "submit_label": "Update limit",
        "cancel_url": "budgets:list"})


@login_required
def allocation_delete(request, pk):
    alloc = get_object_or_404(BudgetAllocation, pk=pk, budget__user=request.user)
    if request.method == "POST":
        budget_id = alloc.budget_id
        alloc.delete()
        messages.success(request, "Category removed from the budget.")
        return redirect("budgets:detail", pk=budget_id)
    return render(request, "confirm_delete.html", {
        "object_label": f"the {alloc.category} limit from {alloc.budget.label}", "cancel_url": "budgets:list"})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted. Your expenses were not affected.")
        return redirect("budgets:list")
    return render(request, "confirm_delete.html", {
        "object_label": f"the whole budget for {budget.label}", "cancel_url": "budgets:list",
        "warning": "Your recorded expenses stay; only the spending limits are removed."})
