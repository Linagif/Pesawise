from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import Category

from . import services
from .forms import PasteForm
from .models import ImportedTransaction


@login_required
def paste(request):
    form = PasteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        r = services.import_text(request.user, form.cleaned_data["text"])
        if r["new"]:
            messages.success(request, f"{r['new']} new message{'s' if r['new'] != 1 else ''} ready to review.")
        if r["duplicates"]:
            messages.info(request, f"{r['duplicates']} message{'s were' if r['duplicates'] != 1 else ' was'} already imported and "
                                   "was skipped, so nothing is counted twice.")
        if r["not_understood"]:
            messages.warning(request, f"{r['not_understood']} message{'s were' if r['not_understood'] != 1 else ' was'} not "
                                      "understood. PesaWise reads M-Pesa confirmation messages for sending, receiving, paying "
                                      "(till and paybill), withdrawing, depositing and buying airtime. Check that you pasted whole messages.")
        if r["new"]:
            return redirect("imports:review")
        return redirect("imports:paste")
    pending = ImportedTransaction.objects.filter(user=request.user, status=ImportedTransaction.PENDING).count()
    return render(request, "imports/paste.html", {"form": form, "pending": pending})


@login_required
def review(request):
    if request.method == "POST":
        r = services.apply_review(request.user, request.POST)
        if r["saved"]:
            messages.success(request, f"{r['saved']} transaction{'s' if r['saved'] != 1 else ''} saved to your records.")
        if r["skipped"]:
            messages.info(request, f"{r['skipped']} skipped.")
        for err in r["errors"]:
            messages.error(request, err)
        return redirect("imports:review")
    rows = services.pending_rows(request.user)
    cats = Category.objects.visible_to(request.user)
    return render(request, "imports/review.html", {
        "rows": rows, "expense_cats": cats.of_type(Category.EXPENSE).exclude(name=services.CHARGES_CATEGORY),
        "income_cats": cats.of_type(Category.INCOME)})


@login_required
@require_POST
def discard(request):
    n = services.discard_pending(request.user)
    messages.info(request, f"{n} waiting message{'s' if n != 1 else ''} discarded. Nothing was added to your records.")
    return redirect("imports:paste")
