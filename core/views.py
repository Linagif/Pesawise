from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm
from .models import Category


@login_required
def category_list(request):
    cats = Category.objects.visible_to(request.user).exclude(category_type=Category.SAVINGS)
    return render(request, "core/categories.html", {
        "expense_cats": cats.of_type(Category.EXPENSE), "income_cats": cats.of_type(Category.INCOME),
        "form": CategoryForm(user=request.user)})


@login_required
def category_add(request):
    form = CategoryForm(request.POST or None, user=request.user, instance=Category(user=request.user))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Category “{form.instance.name}” added.")
        return redirect("core:list")
    if request.method == "POST":
        messages.error(request, "Could not add the category: " + "; ".join(
            e for errs in form.errors.values() for e in errs))
    return redirect("core:list")


@login_required
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)   # defaults and others' categories -> 404
    if request.method == "POST":
        try:
            cat.delete()
            messages.success(request, f"Category “{cat.name}” deleted.")
        except ProtectedError:
            messages.error(request, "This category is used by existing records, so it cannot be deleted.")
        return redirect("core:list")
    return render(request, "confirm_delete.html", {
        "object_label": f"the category “{cat.name}”", "cancel_url": "core:list"})
