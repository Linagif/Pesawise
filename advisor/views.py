from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import simulator as sim
from .analysis import build_health_report
from .forms import AffordForm, CutForm, IncomeChangeForm, SaveForm
from .models import Recommendation
from .recommendations import outcome, refresh_recommendations
from .rules import generate_tips


@login_required
def tips(request):
    """Financial Health page: verified indicators + insights, then the rule-based alerts."""
    today = timezone.localdate()
    period = "last" if request.GET.get("period") == "last" else "this"
    refresh_recommendations(request.user, today)
    pending = Recommendation.objects.filter(user=request.user, is_active=True, status=Recommendation.PENDING).count()
    return render(request, "advisor/tips.html", {
        "health": build_health_report(request.user, today, period),
        "tips": generate_tips(request.user, today), "pending_count": pending})


SCENARIO_FORMS = {"afford": AffordForm, "save": SaveForm, "cut": CutForm, "income": IncomeChangeForm}


@login_required
def simulator(request):
    """What-if simulator. Read-only: nothing here ever changes the student's records."""
    user, today = request.user, timezone.localdate()
    base = sim.baseline(user, today)
    chosen = request.GET.get("scenario")
    forms = {}
    result = None
    for key, cls in SCENARIO_FORMS.items():
        forms[key] = cls(request.GET, user=user) if key == chosen else cls(user=user)
    if base and chosen in SCENARIO_FORMS and forms[chosen].is_valid():
        cd = forms[chosen].cleaned_data
        if chosen == "afford":
            result = sim.can_afford(base, cd["price"], today, cd["months"])
        elif chosen == "save":
            result = sim.save_plan(base, today, cd["monthly"], cd["target"])
        elif chosen == "cut":
            cat = cd["category"]
            result = sim.cut_category(base, today, cat.name, cat.spending_type == "ESSENTIAL", cd["reduction"])
        else:
            result = sim.income_change(base, today, cd["direction"], cd["mode"], cd["value"])
    return render(request, "advisor/simulator.html", {
        "base": base, "forms": forms, "result": result, "chosen": chosen,
        "scenarios": [("afford", "Can I afford it?", "bi-bag"), ("save", "Saving plan", "bi-piggy-bank"),
                      ("cut", "Spend less", "bi-scissors"), ("income", "Income changes", "bi-graph-up-arrow")]})


@login_required
def recommendations(request):
    """Stored recommendations. Opening the page refreshes them (idempotent) from the student's current records."""
    today = timezone.localdate()
    qs = refresh_recommendations(request.user, today)
    active = [{"rec": r, "outcome": outcome(r, today)} for r in
              qs.filter(is_active=True, status__in=[Recommendation.PENDING, Recommendation.ACCEPTED])
                .order_by("status", "-priority", "id")]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    active.sort(key=lambda x: (x["rec"].status != Recommendation.PENDING, rank[x["rec"].priority]))
    history = [{"rec": r, "outcome": outcome(r, today)} for r in
               qs.filter(status__in=[Recommendation.COMPLETED, Recommendation.DISMISSED]).order_by("-status_changed_at")]
    return render(request, "advisor/recommendations.html", {"active": active, "history": history})


@login_required
@require_POST
def recommendation_status(request, pk):
    rec = get_object_or_404(Recommendation, pk=pk, user=request.user)      # other students' items -> 404
    new = request.POST.get("status")
    if new not in Recommendation.STATUSES:
        messages.error(request, "That action is not valid.")
    elif new != rec.status:
        rec.set_status(new)
        messages.success(request, {"ACCEPTED": "Recommendation accepted. We will show what happens to your spending.",
                                   "DISMISSED": "Recommendation dismissed. It will not come back for a while.",
                                   "COMPLETED": "Marked as completed. Well done!",
                                   "PENDING": "Recommendation reopened."}[new])
    return redirect("advisor:recommendations")


@login_required
@require_POST
def recommendation_feedback(request, pk):
    rec = get_object_or_404(Recommendation, pk=pk, user=request.user)
    answer = request.POST.get("useful")
    if answer in ("yes", "no"):
        rec.useful = answer == "yes"
        rec.save(update_fields=["useful"])
        messages.success(request, "Thanks for the feedback.")
    else:
        messages.error(request, "That answer is not valid.")
    return redirect("advisor:recommendations")
