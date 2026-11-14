from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.templatetags.money import kes
from dashboard import services

from .forms import ContributionForm, GoalForm
from .models import SavingsContribution, SavingsGoal


@login_required
def goal_list(request):
    goals = SavingsGoal.objects.filter(user=request.user)
    return render(request, "savings/list.html", {"goals": goals, "total_saved": services.total_savings(request.user)})


@login_required
def goal_add(request):
    form = GoalForm(request.POST or None, user=request.user, instance=SavingsGoal(user=request.user))
    if request.method == "POST" and form.is_valid():
        goal = form.save()
        messages.success(request, f"Savings goal “{goal.name}” created.")
        return redirect("savings:detail", pk=goal.pk)
    return render(request, "form_page.html", {"title": "New savings goal", "form": form,
                                              "submit_label": "Create goal", "cancel_url": "savings:list"})


@login_required
def goal_detail(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    form = ContributionForm(request.POST or None, user=request.user, instance=SavingsContribution(goal=goal))
    if request.method == "POST" and form.is_valid():
        c = form.save()
        messages.success(request, f"{kes(c.amount)} added to “{goal.name}”. "
                                  f"Available balance: {kes(services.available_balance(request.user))}.")
        if goal.is_complete:
            messages.success(request, f"🎉 You have reached your goal “{goal.name}”!")
        if services.available_balance(request.user) < 0:
            messages.warning(request, "This contribution is more than your recorded available balance. "
                                      "Make sure all your income is recorded.")
        return redirect("savings:detail", pk=goal.pk)
    return render(request, "savings/detail.html", {"goal": goal, "form": form,
                                                   "contributions": goal.contributions.all()})


@login_required
def goal_edit(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    form = GoalForm(request.POST or None, user=request.user, instance=goal)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Savings goal updated.")
        return redirect("savings:detail", pk=goal.pk)
    return render(request, "form_page.html", {"title": "Edit savings goal", "form": form,
                                              "submit_label": "Update goal", "cancel_url": "savings:list"})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == "POST":
        goal.delete()
        messages.success(request, "Savings goal deleted.")
        return redirect("savings:list")
    return render(request, "confirm_delete.html", {
        "object_label": f"the goal “{goal.name}” and all its contributions", "cancel_url": "savings:list",
        "warning": "Its contributions will no longer be counted as savings transfers, so your available balance will increase."})


@login_required
def contribution_edit(request, pk):
    c = get_object_or_404(SavingsContribution, pk=pk, goal__user=request.user)
    form = ContributionForm(request.POST or None, user=request.user, instance=c)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contribution updated.")
        return redirect("savings:detail", pk=c.goal_id)
    return render(request, "form_page.html", {"title": "Edit contribution", "form": form,
                                              "submit_label": "Update contribution", "cancel_url": "savings:list"})


@login_required
def contribution_delete(request, pk):
    c = get_object_or_404(SavingsContribution, pk=pk, goal__user=request.user)
    if request.method == "POST":
        goal_id = c.goal_id
        c.delete()
        messages.success(request, "Contribution deleted.")
        return redirect("savings:detail", pk=goal_id)
    return render(request, "confirm_delete.html", {
        "object_label": f"the contribution of {kes(c.amount)} on {c.contribution_date:%d %b %Y}",
        "cancel_url": "savings:list"})
