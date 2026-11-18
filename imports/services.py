"""Import workflow: paste -> PENDING rows -> student review -> real Expense/Income records.

Safety rules
  * Nothing becomes an Expense or Income until the student confirms it.
  * A category is only ever PRE-SELECTED from facts: the message says 'airtime', or the student already confirmed a
    category for the same recipient. Unknown recipients get no suggestion.
  * The M-Pesa reference is unique per student, so pasting the same message again never creates a second copy.
  * Each confirmed row is saved in its own database transaction; one bad row never blocks the others.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Category
from expenses.models import Expense
from income.models import Income

from . import parser as p
from .models import ImportedTransaction as IT

CHARGES_CATEGORY = "Transaction charges"


# ------------------------------------------------------------------ paste
def import_text(user, text, today=None):
    """Parse pasted text and store new messages as PENDING. Returns counts; never raises for bad content."""
    parsed, not_understood = p.parse_many(text, today)
    new = duplicates = 0
    seen = set()
    for m in parsed:
        if m.reference in seen:
            duplicates += 1
            continue
        seen.add(m.reference)
        try:
            with transaction.atomic():
                IT.objects.create(user=user, reference=m.reference, kind=m.kind, amount=m.amount, charge=m.charge,
                                  counterparty=m.counterparty, occurred_on=m.occurred_on, occurred_time=m.occurred_time,
                                  reversal_of=m.reversal_of)
            new += 1
        except IntegrityError:                    # already imported (pending, saved or skipped)
            duplicates += 1
    return {"new": new, "duplicates": duplicates, "not_understood": not_understood}


# ------------------------------------------------------------------ review helpers
def suggest(user, row):
    """(category, reason) or (None, ''). Only evidence-based suggestions."""
    if row.kind == p.AIRTIME:
        c = Category.objects.filter(user__isnull=True, name="Internet and airtime", category_type=Category.EXPENSE).first()
        return c, "The message says this was an airtime purchase."
    if row.kind == p.REVERSAL:
        c = Category.objects.filter(user__isnull=True, name="Other", category_type=Category.INCOME).first()
        return c, "A reversal returns money to you."
    if row.kind in IT.CASH_KINDS or not row.counterparty:
        return None, ""
    earlier = (IT.objects.filter(user=user, status=IT.IMPORTED, counterparty__iexact=row.counterparty, kind=row.kind)
               .exclude(pk=row.pk).order_by("-resolved_at"))
    for e in earlier:
        rec = e.expense if row.group == "expense" else e.income
        if rec is not None:
            return (rec.category if row.group == "expense" else rec.source), "You used this category for the same recipient before."
    return None, ""


def possible_duplicate(user, row):
    """True if the student probably recorded this by hand already (same amount on the same day)."""
    if row.group == "expense":
        linked = IT.objects.filter(user=user).exclude(expense=None).values("expense_id")
        return Expense.objects.filter(user=user, amount=row.amount, expense_date=row.occurred_on).exclude(pk__in=linked).exists()
    if row.group == "income":
        linked = IT.objects.filter(user=user).exclude(income=None).values("income_id")
        return Income.objects.filter(user=user, amount=row.amount, date_received=row.occurred_on).exclude(pk__in=linked).exists()
    return False


def reversal_original_known(user, row):
    return row.kind == p.REVERSAL and IT.objects.filter(user=user, reference=row.reversal_of, status=IT.IMPORTED).exists()


def pending_rows(user):
    rows = []
    for r in IT.objects.filter(user=user, status=IT.PENDING):
        cat, reason = suggest(user, r)
        rows.append({"row": r, "suggested": cat, "reason": reason, "duplicate": possible_duplicate(user, r),
                     "original_known": reversal_original_known(user, r)})
    return rows


def _charges_category():
    c, _ = Category.objects.get_or_create(user=None, name=CHARGES_CATEGORY, category_type=Category.EXPENSE,
                                          defaults={"spending_type": Category.ESSENTIAL})
    return c


# ------------------------------------------------------------------ apply the student's decisions
def apply_review(user, post):
    """post = request.POST. Per row: action_<id> in {save, skip, later} and category_<id>.
    Returns {'saved': n, 'skipped': n, 'errors': [str]}."""
    result = {"saved": 0, "skipped": 0, "errors": []}
    for row in IT.objects.filter(user=user, status=IT.PENDING):
        action = post.get(f"action_{row.pk}", "later")
        if action == "skip":
            row.status, row.resolved_at = IT.SKIPPED, timezone.now()
            row.save(update_fields=["status", "resolved_at"])
            result["skipped"] += 1
        elif action == "save":
            try:
                _save_row(user, row, post.get(f"category_{row.pk}"))
                result["saved"] += 1
            except ValidationError as exc:
                result["errors"].append(f"{row.reference}: {'; '.join(exc.messages)}")
    return result


def _save_row(user, row, category_id):
    note = f"Imported from M-Pesa message {row.reference}"
    category = None
    if row.group in ("expense", "income"):
        wanted = Category.EXPENSE if row.group == "expense" else Category.INCOME
        try:
            category = (Category.objects.visible_to(user).of_type(wanted).get(pk=int(category_id)))
        except (TypeError, ValueError, Category.DoesNotExist):
            raise ValidationError("Choose a category before saving.")
    with transaction.atomic():
        if row.group == "expense":
            e = Expense(user=user, category=category, amount=row.amount, description=row.description,
                        expense_date=row.occurred_on, payment_method=Expense.MPESA, is_planned=True, notes=note)
            e.full_clean(); e.save()
            row.expense = e
        elif row.group == "income":
            i = Income(user=user, source=category, amount=row.amount, description=row.description,
                       date_received=row.occurred_on, notes=note)
            i.full_clean(); i.save()
            row.income = i
        if row.charge > 0:       # the fee is a real cost, recorded separately so the main amount stays exact
            c = Expense(user=user, category=_charges_category(), amount=row.charge, description=f"M-Pesa charge ({row.reference})",
                        expense_date=row.occurred_on, payment_method=Expense.MPESA, is_planned=True, notes=note)
            c.full_clean(); c.save()
            row.charge_expense = c
        row.status, row.resolved_at = IT.IMPORTED, timezone.now()
        row.save()


def discard_pending(user):
    deleted, _ = IT.objects.filter(user=user, status=IT.PENDING).delete()
    return deleted
