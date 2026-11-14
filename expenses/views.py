from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.templatetags.money import kes
from core.utils import money, safe_next
from dashboard import services

from .forms import ExpenseFilterForm, ExpenseForm
from .models import Expense


def _after_save_messages(request, expense):
    balance = services.available_balance(request.user)
    messages.success(request, f"Expense of {kes(expense.amount)} saved. Available balance: {kes(balance)}.")
    alert = services.category_budget_alert(request.user, expense.category, expense.expense_date)
    if alert:
        level, text = alert
        (messages.error if level == "danger" else messages.warning)(request, text)
    if balance < 0:
        messages.warning(request, "Your available balance is now negative: you have recorded more spending "
                                  "than money received. Check that all your income is recorded.")


@login_required
def expense_list(request):
    qs = Expense.objects.filter(user=request.user).select_related("category")
    form = ExpenseFilterForm(request.GET or None, user=request.user)
    if form.is_valid():
        cd = form.cleaned_data
        if cd.get("q"):
            qs = qs.filter(description__icontains=cd["q"])
        if cd.get("category"):
            qs = qs.filter(category=cd["category"])
        if cd.get("payment_method"):
            qs = qs.filter(payment_method=cd["payment_method"])
        if cd.get("planned") in ("0", "1"):
            qs = qs.filter(is_planned=cd["planned"] == "1")
        if cd.get("start"):
            qs = qs.filter(expense_date__gte=cd["start"])
        if cd.get("end"):
            qs = qs.filter(expense_date__lte=cd["end"])
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    today = timezone.localdate()
    return render(request, "expenses/list.html", {
        "page": page, "form": form, "filtered_total": money(qs.aggregate(t=Sum("amount"))["t"]),
        "totals": services.spend_totals(request.user, today), "querystring": query.urlencode()})


@login_required
def expense_daily(request):
    today = timezone.localdate()
    day = parse_date(request.GET.get("date", "") or "") or today
    day = min(day, today)
    items = Expense.objects.filter(user=request.user, expense_date=day).select_related("category")
    return render(request, "expenses/daily.html", {
        "day": day, "is_today": day == today, "prev_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1) if day < today else None,
        "items": items, "summary": services.daily_summary(request.user, day),
        "totals": services.spend_totals(request.user, day)})


@login_required
def expense_add(request):
    form = ExpenseForm(request.POST or None, user=request.user, instance=Expense(user=request.user))
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        _after_save_messages(request, obj)
        if "save_another" in request.POST:
            return redirect("expenses:add")
        return redirect(safe_next(request, "expenses:daily"))
    return render(request, "form_page.html", {
        "title": "Record daily expense", "form": form, "submit_label": "Save expense",
        "cancel_url": "expenses:daily", "save_another": True, "next": request.POST.get("next", "")})


@login_required
def expense_edit(request, pk):
    obj = get_object_or_404(Expense, pk=pk, user=request.user)
    form = ExpenseForm(request.POST or None, user=request.user, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Expense updated. Your balance and budgets have been recalculated.")
        return redirect(safe_next(request, "expenses:list"))
    return render(request, "form_page.html", {
        "title": "Edit expense", "form": form, "submit_label": "Update expense", "cancel_url": "expenses:list"})


@login_required
def expense_delete(request, pk):
    obj = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Expense deleted. Your balance has been recalculated.")
        return redirect(safe_next(request, "expenses:list"))
    return render(request, "confirm_delete.html", {
        "object_label": f"the expense “{obj.description}” of {kes(obj.amount)} on {obj.expense_date:%d %b %Y}",
        "cancel_url": "expenses:list", "warning": "Deleting it will increase your available balance."})
