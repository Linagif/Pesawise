"""Recommendation engine: turns verified analysis (Stage 1) and baseline figures (Stage 2) into stored,
evidence-backed recommendations.

Safety rules built into every rule:
  * No recommendation at all without at least one full month of history.
  * Money is only ever suggested out of FREE cash (income - spending - what you already save), never out of essentials.
  * Essential categories are never told to 'cut'; they get a 'review' suggestion with no amount.
  * Every recommendation carries the numbers it was based on, a confidence level and a review date.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from core.models import Category
from core.utils import ZERO, money
from . import analysis as an
from . import simulator as sim
from .models import Recommendation

COOLDOWN_DAYS = 30          # a dismissed/completed recommendation is not re-suggested for this long
REVIEW_DAYS = 30
REVIEW_DAYS_HIGH = 14
MIN_SUGGESTION = Decimal("50")
FREE_CASH_SHARE = Decimal("0.5")          # never suggest committing more than half of free cash
EMERGENCY_FIRST_MILESTONE = Decimal("1")
EMERGENCY_TARGET = Decimal("3")
SMALL_PURCHASE_REDUCTION = Decimal("0.8")  # suggest a weekly limit 20% below the recent level


def round50(value):
    """Round to the nearest KSh 50 (never below 50)."""
    v = (Decimal(value) / 50).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 50
    return max(MIN_SUGGESTION, v)


def _confidence(months_used):
    if months_used >= 3:
        return Recommendation.HIGH, "Based on 3 or more full months of your records."
    if months_used == 2:
        return Recommendation.MEDIUM, "Based on 2 full months of your records."
    return Recommendation.LOW, "Based on only 1 full month of your records, so it may change."


def _cand(key, title, observation, evidence, explanation, action, priority, confidence, confidence_note,
          amount=None, impact="", category=None, baseline=None):
    return {"key": key[:100], "title": title, "observation": observation, "evidence": evidence,
            "explanation": explanation, "action": action, "priority": priority, "confidence": confidence,
            "confidence_note": confidence_note, "suggested_amount": amount, "estimated_impact": impact,
            "category": category, "baseline_monthly": baseline}


def _category_obj(user, name):
    return Category.objects.visible_to(user).filter(name=name, category_type=Category.EXPENSE).first()


def build_candidates(user, today):
    b = sim.baseline(user, today)
    if b is None:
        return []                                  # not enough history: say nothing rather than guess
    conf, conf_note = _confidence(b["months_used"])
    out = []

    # 1. Spending more than income -------------------------------------------------
    if b["income"] > 0 and b["surplus"] < 0:
        gap = money(-b["surplus"])
        disc = [c for c in Category.objects.visible_to(user).filter(
            category_type=Category.EXPENSE, spending_type=Category.DISCRETIONARY, name__in=b["category_avg"].keys())]
        top = sorted(disc, key=lambda c: b["category_avg"][c.name], reverse=True)[:2]
        amount = min(gap, round50(b["discretionary"] * FREE_CASH_SHARE)) if b["discretionary"] >= MIN_SUGGESTION else None
        names = " and ".join(c.name for c in top) if top else "your discretionary categories"
        out.append(_cand(
            "negative_cashflow", "Your spending is higher than your income",
            f"On average you spent {an.kes(b['spent'])} a month but received {an.kes(b['income'])}.",
            f"Average gap: {an.kes(gap)} a month over {b['months_used']} full month{'s' if b['months_used'] != 1 else ''}.",
            "When spending is higher than income, the difference has to come from savings, borrowing or unpaid bills, "
            "which cannot continue for long.",
            f"Start with {names}: set a monthly limit and track it. If essentials alone exceed your income, look at ways to "
            "raise income and talk to your university's student support office.",
            Recommendation.HIGH, conf, conf_note, amount,
            (f"Cutting {an.kes(amount)} a month would close about {an.pct(amount, gap)}% of the gap." if amount else
             "No discretionary spending was recorded, so the gap cannot be closed by cutting wants."), None, None))

    # 2. Categories that rose ------------------------------------------------------
    ch = an.category_changes(user, today)
    if ch["available"]:
        for r in [r for r in ch["rows"] if r["direction"] == "up" and not r["is_new"]][:3]:
            cat = _category_obj(user, r["category"])
            essential = cat is not None and cat.spending_type == Category.ESSENTIAL
            amount = None if essential else round50(r["diff"])
            out.append(_cand(
                f"category_rise:{r['category']}", f"Review your {r['category']} spending",
                f"{r['category']} spending rose {r['pct']}% from {ch['from_label']} to {ch['to_label']}.",
                f"{an.kes(r['before'])} in {ch['from_label']} → {an.kes(r['after'])} in {ch['to_label']} (up {an.kes(r['diff'])}).",
                "A one-off purchase is normal, but a rise that continues can quietly reduce what is left for savings.",
                (f"Check whether the rise was a one-off. {r['category']} is an essential category, so only trim it if you can do so "
                 "without hurting your wellbeing or studies." if essential else
                 f"Check whether the rise was a one-off. If not, set a monthly limit of about {an.kes(r['before'])} for {r['category']}."),
                Recommendation.LOW if essential else Recommendation.MEDIUM, Recommendation.MEDIUM,
                "Based on a comparison of 2 full months.", amount,
                "" if essential else f"Returning to {ch['from_label']}'s level would free up about {an.kes(amount)} a month.",
                cat, r["after"]))

    # 3. Emergency fund / 4. savings rate (only from FREE cash) --------------------
    free = b["free"]
    fund = an.emergency_fund(user, today)
    made_savings_rec = False
    if fund and fund["months"] < EMERGENCY_TARGET and free >= MIN_SUGGESTION:
        milestone = EMERGENCY_FIRST_MILESTONE if fund["months"] < EMERGENCY_FIRST_MILESTONE else EMERGENCY_TARGET
        needed = money(milestone * fund["avg_essential"] - fund["saved"])
        monthly = min(round50(free * FREE_CASH_SHARE), free)
        months = sim._ceil_div(needed, monthly) if needed > 0 else 0
        out.append(_cand(
            "emergency_fund", "Build your emergency fund",
            f"Your savings would cover about {fund['months']} month{'s' if fund['months'] != 1 else ''} of essential spending.",
            f"{an.kes(fund['saved'])} saved ÷ {an.kes(fund['avg_essential'])} average monthly essentials. "
            f"Free cash after your current saving: {an.kes(free)} a month.",
            "An emergency fund lets you handle a lost income or an unexpected bill without borrowing. Many advisers suggest "
            "3 months of essentials; a first goal of 1 month is a good start.",
            f"Set aside {an.kes(monthly)} a month (less than half of your free cash) toward a savings goal for emergencies.",
            Recommendation.HIGH if fund["months"] < EMERGENCY_FIRST_MILESTONE else Recommendation.MEDIUM, conf, conf_note, monthly,
            f"At this pace you would reach {milestone} month{'s' if milestone != 1 else ''} of cover in about {months} month{'s' if months != 1 else ''}."
            if months else "", None, None))
        made_savings_rec = True
    if not made_savings_rec and b["income"] > 0 and free >= MIN_SUGGESTION:
        rate = an.pct(b["saved"], b["income"]) or Decimal("0")
        if rate < an.SAVINGS_RATE_GOOD:
            gap_to_goal = money(b["income"] * an.SAVINGS_RATE_GOOD / 100 - b["saved"])
            monthly = min(round50(free * FREE_CASH_SHARE), round50(gap_to_goal)) if gap_to_goal >= MIN_SUGGESTION else None
            if monthly:
                out.append(_cand(
                    "savings_rate", "Increase your monthly savings gradually",
                    f"You save about {rate}% of your income.",
                    f"{an.kes(b['saved'])} saved on average out of {an.kes(b['income'])} income. Free cash after saving: {an.kes(free)}.",
                    "Saving a little more each month builds a cushion for goals and emergencies. A common guideline is around 10% of income, "
                    "though the right level depends on your situation.",
                    f"Add {an.kes(monthly)} a month to your savings.", Recommendation.MEDIUM, conf, conf_note, monthly,
                    f"Over a year that would add {an.kes(monthly * 12)} to your savings.", None, None))

    # 5. Small purchases ------------------------------------------------------------
    sp = an.small_purchases(user, today)
    if sp["fired"]:
        weekly_now = money(sp["total"] / 30 * 7)
        limit = round50(weekly_now * SMALL_PURCHASE_REDUCTION)
        out.append(_cand(
            "small_purchases", "Set a weekly limit for small purchases",
            f"You made {sp['count']} purchases of {an.kes(sp['limit'])} or less in the last 30 days.",
            f"They add up to {an.kes(sp['total'])}, which is {sp['share']}% of your spending (about {an.kes(weekly_now)} a week).",
            "Each small purchase feels harmless, but together they can be a large part of your spending.",
            f"Try a weekly limit of about {an.kes(limit)} for small purchases and see how it feels.",
            Recommendation.LOW, Recommendation.MEDIUM, "Based on the last 30 days.", limit,
            f"If you kept to it, you would spend about {an.kes(money(sp['total'] * (1 - SMALL_PURCHASE_REDUCTION)))} less over a month.", None, None))

    # 6. Recurring payments ---------------------------------------------------------
    for r in an.recurring_payments(user, today)[:3]:
        out.append(_cand(
            f"recurring:{an._normalise(r['description'])}", f"Check the recurring payment “{r['description']}”",
            f"“{r['description']}” appeared in {r['months_seen']} different months.",
            f"Usually around {an.kes(r['typical'])} ({r['category']}); last seen {r['last_date']:%d %b %Y}.",
            "Regular payments are easy to forget. Checking them occasionally avoids paying for things you no longer use.",
            "Confirm you still use it. If not, stop it; if you do, make sure it is in your budget.",
            Recommendation.LOW, Recommendation.MEDIUM if r["months_seen"] >= 4 else Recommendation.LOW,
            "Detected from a repeating pattern, so please confirm it really is recurring.", r["typical"],
            f"Stopping it would free up about {an.kes(r['typical'])} a month.", None, None))
    return out


# ------------------------------------------------------------------ persistence
def _apply(rec, c, today):
    for f in ("title", "observation", "evidence", "explanation", "action", "priority", "confidence", "confidence_note",
              "suggested_amount", "estimated_impact", "category", "baseline_monthly"):
        setattr(rec, f, c[f])
    rec.is_active = True


def _review_date(priority, today):
    return today + timedelta(days=REVIEW_DAYS_HIGH if priority == Recommendation.HIGH else REVIEW_DAYS)


def refresh_recommendations(user, today=None):
    """Idempotent: creates new recommendations, refreshes pending ones, never touches accepted ones,
    and does not nag about dismissed/completed ones during the cooldown."""
    today = today or timezone.localdate()
    now = timezone.now()
    candidates = build_candidates(user, today)
    existing = {r.key: r for r in Recommendation.objects.filter(user=user)}
    seen = set()
    for c in candidates:
        seen.add(c["key"])
        rec = existing.get(c["key"])
        if rec is None:
            rec = Recommendation(user=user, key=c["key"], generated_on=today, review_date=_review_date(c["priority"], today))
            _apply(rec, c, today)
            rec.save()
        elif rec.status == Recommendation.PENDING:
            _apply(rec, c, today)
            rec.save()
        elif rec.status == Recommendation.ACCEPTED:
            if not rec.is_active:
                rec.is_active = True
                rec.save(update_fields=["is_active"])
        else:   # dismissed or completed: only come back after the cooldown, and only if it still applies
            changed = rec.status_changed_at or rec.created_at
            if now - changed >= timedelta(days=COOLDOWN_DAYS):
                _apply(rec, c, today)
                rec.status, rec.useful, rec.accepted_at, rec.status_changed_at = Recommendation.PENDING, None, None, None
                rec.generated_on, rec.review_date = today, _review_date(c["priority"], today)
                rec.save()
    for key, rec in existing.items():
        if key not in seen and rec.status == Recommendation.PENDING and rec.is_active:
            rec.is_active = False                       # the trigger has gone away: hide, keep for history
            rec.save(update_fields=["is_active"])
    return Recommendation.objects.filter(user=user)


# ------------------------------------------------------------------ outcome tracking
OUTCOME_MIN_DAYS = 14


def outcome(rec, today):
    """What happened to the category's spending since the student accepted the recommendation.
    Descriptive only: it never claims the recommendation caused the change."""
    if rec.status not in (Recommendation.ACCEPTED, Recommendation.COMPLETED) or not rec.category_id \
            or rec.baseline_monthly is None or rec.accepted_at is None:
        return None
    start = timezone.localtime(rec.accepted_at).date()
    days = (today - start).days + 1
    if days < OUTCOME_MIN_DAYS:
        return {"ready": False, "text": f"Too early to tell. Check back after {OUTCOME_MIN_DAYS} days "
                                        f"(it has been {days})."}
    total = an._expenses(rec.user, start, today).filter(category=rec.category)
    from django.db.models import Sum
    spent = money(total.aggregate(t=Sum("amount"))["t"])
    per_month = money(spent / days * 30)
    base = rec.baseline_monthly
    change = an.pct(per_month - base, base) if base else None
    word = "about the same as" if change is not None and abs(change) < 5 else ("lower than" if per_month < base else "higher than")
    return {"ready": True, "per_month": per_month, "baseline": base, "change_pct": change, "days": days,
            "text": (f"Since you accepted this on {start:%d %b %Y} ({days} days), your {rec.category.name} spending is running at "
                     f"about {an.kes(per_month)} a month, {word} the {an.kes(base)} it was before. Other things may also have "
                     "changed, so this does not prove the recommendation caused it.")}
