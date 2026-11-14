from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.templatetags.money import kes
from core.utils import money, safe_next
from dashboard import services

from .forms import IncomeFilterForm, IncomeForm
from .models import Income


@login_required
def income_list(request):
    qs = Income.objects.filter(user=request.user).select_related("source")
    form = IncomeFilterForm(request.GET or None, user=request.user)
    if form.is_valid():
        cd = form.cleaned_data
        if cd.get("source"):
            qs = qs.filter(source=cd["source"])
        if cd.get("start"):
            qs = qs.filter(date_received__gte=cd["start"])
        if cd.get("end"):
            qs = qs.filter(date_received__lte=cd["end"])
    filtered_total = money(qs.aggregate(t=Sum("amount"))["t"])
    by_source = list(qs.values("source__name").annotate(total=Sum("amount")).order_by("-total"))
    for row in by_source:
        row["share"] = int(row["total"] / filtered_total * 100) if filtered_total else 0
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "income/list.html", {
        "page": page, "form": form, "filtered_total": filtered_total, "by_source": by_source,
        "all_time_total": services.total_income(request.user), "querystring": query.urlencode()})


@login_required
def income_add(request):
    form = IncomeForm(request.POST or None, user=request.user, instance=Income(user=request.user))
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Income of {kes(obj.amount)} recorded. "
                                  f"Available balance: {kes(services.available_balance(request.user))}.")
        if "save_another" in request.POST:
            return redirect("income:add")
        return redirect(safe_next(request, "income:list"))
    return render(request, "form_page.html", {
        "title": "Record income", "form": form, "submit_label": "Save income",
        "cancel_url": "income:list", "save_another": True})


@login_required
def income_edit(request, pk):
    obj = get_object_or_404(Income, pk=pk, user=request.user)
    form = IncomeForm(request.POST or None, user=request.user, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Income record updated.")
        return redirect("income:list")
    return render(request, "form_page.html", {
        "title": "Edit income", "form": form, "submit_label": "Update income", "cancel_url": "income:list"})


@login_required
def income_delete(request, pk):
    obj = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Income record deleted. Your balance has been recalculated.")
        return redirect("income:list")
    return render(request, "confirm_delete.html", {
        "object_label": f"the income of {kes(obj.amount)} ({obj.description}) from {obj.date_received:%d %b %Y}",
        "cancel_url": "income:list",
        "warning": "Deleting it will reduce your total income and available balance."})
