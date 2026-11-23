"""What-if simulator: deterministic arithmetic on a student's own recent history.

Everything starts from baseline(): the AVERAGE of up to the last 3 COMPLETE months. Each scenario function
takes that baseline plus the student's inputs and returns the same shape of result:
    verdict ('good' | 'tight' | 'no' | 'info'), headline, calculations, assumptions, notes, table, limitations.
No scenario can change any data. Results are simulations, never guarantees.
"""
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from core.utils import ZERO, add_months, money, month_range
from dashboard import services as svc

from . import analysis as an

import calendar

BASELINE_MONTHS = 3
TIGHT_CUT_MAX_PCT = Decimal("50")     # cutting more than half of a category is unlikely to last
GOOD_CUT_MAX_PCT = Decimal("25")
MAX_MONTHS_SHOWN = 600                # beyond 50 years we just say "not realistic"
SURPLUS_COMFORT_PCT = Decimal("10")   # a surplus under 10% of income counts as thin
RECOVERY_MONTHS_LIMIT = 12

LIMITATIONS = [
    "This is a simulation based on your averages from recent full months. Your real future may differ.",
    "It cannot know about future income, bills, emergencies or price changes.",
    "It is a planning aid, not a guarantee and not professional financial advice.",
]


def kes(v):
    return an.kes(v)


def _ceil_div(a, b):
    return int((Decimal(a) / Decimal(b)).to_integral_value(rounding=ROUND_CEILING))


def _month_label(today, months_ahead):
    y, m = add_months(today.year, today.month, months_ahead)
    return f"{calendar.month_name[m]} {y}"


# ------------------------------------------------------------------ baseline
def baseline(user, today):
    """Average month from up to the last 3 complete months that have any income or spending. None if there are none."""
    used, cat_sums = [], {}
    for back in range(1, BASELINE_MONTHS + 1):
        y, m = add_months(today.year, today.month, -back)
        start, end = month_range(y, m)
        income, spent = svc.total_income(user, start, end), svc.total_expenses(user, start, end)
        if income <= 0 and spent <= 0:
            continue
        split = an.essential_split(user, start, end)
        used.append({"income": income, "spent": spent, "essential": split["essential"],
                     "discretionary": split["discretionary"], "saved": svc.total_savings_transfers(user, start, end)})
        for name, total in an._category_totals(user, start, end).items():
            cat_sums[name] = cat_sums.get(name, ZERO) + total
    if not used:
        return None
    n = len(used)
    avg = lambda key: money(sum((u[key] for u in used), ZERO) / n)   # noqa: E731
    surplus_list = [u["income"] - u["spent"] for u in used]
    b = {"months_used": n, "income": avg("income"), "spent": avg("spent"), "essential": avg("essential"),
         "discretionary": avg("discretionary"), "saved": avg("saved"),
         "category_avg": {name: money(total / n) for name, total in cat_sums.items()},
         "balance": svc.available_balance(user), "savings": svc.total_savings(user),
         "surplus_min": money(min(surplus_list)), "surplus_max": money(max(surplus_list))}
    b["surplus"] = money(b["income"] - b["spent"])              # before anything goes into savings
    b["free"] = money(b["surplus"] - b["saved"])                # what is left after your current saving habit
    return b


def _result(title, verdict, headline, calcs, assumptions, notes=None, table=None):
    return {"title": title, "verdict": verdict, "headline": headline, "calcs": calcs, "assumptions": assumptions,
            "notes": notes or [], "table": table, "limitations": LIMITATIONS}


# ------------------------------------------------------------------ 1. Can I afford a purchase?
def can_afford(b, price, today, months=None):
    price = money(price)
    balance, free = b["balance"], b["free"]
    shortfall = money(max(ZERO, price - balance))
    calcs = [("Price", kes(price)), ("Available balance now", kes(balance)),
             ("Free cash per month after your current saving habit", kes(free))]
    assumptions = ["Your available balance is income minus expenses minus savings you have recorded. Money inside your "
                   "savings goals is not touched.",
                   "Free cash per month is your recent average income, minus average spending, minus what you usually save."]
    notes = []
    if months is None:
        if balance >= price:
            after = money(balance - price)
            buffer = b["essential"]
            calcs.append(("Balance after buying", kes(after)))
            calcs.append(("One month of essential spending", kes(buffer)))
            if after >= buffer:
                verdict, head = "good", "You could pay from your available balance and still keep at least a month of essential spending."
            else:
                verdict, head = "tight", ("You could pay now, but it would leave less than a month of essential spending "
                                          f"({kes(after)} left against about {kes(buffer)} needed).")
        else:
            calcs.append(("Shortfall today", kes(shortfall)))
            if free > 0:
                n = _ceil_div(shortfall, free)
                calcs.append(("Months to cover the shortfall at that pace", str(n)))
                if n > MAX_MONTHS_SHOWN:
                    verdict, head = "no", "At your recent pace this would take longer than is realistic to plan for."
                else:
                    verdict = "tight" if n <= RECOVERY_MONTHS_LIMIT else "no"
                    head = (f"You cannot pay for this from your balance today. At your recent free cash you could close the "
                            f"{kes(shortfall)} gap in about {n} month{'s' if n != 1 else ''} (around {_month_label(today, n)}).")
            else:
                verdict, head = "no", ("You cannot pay from your balance today, and your recent figures leave no free cash each "
                                       "month to close the gap.")
    else:
        calcs.append(("Months until you want to buy", str(months)))
        if shortfall == 0:
            verdict, head = "good", "Your available balance already covers this."
        else:
            required = money(shortfall / months)
            cut = money(max(ZERO, required - free))
            calcs += [("Shortfall to save", kes(shortfall)), ("Needed per month", kes(required))]
            if required <= free:
                verdict, head = "good", f"Saving {kes(required)} a month fits within your recent free cash."
            elif required <= free + b["discretionary"]:
                verdict = "tight"
                head = (f"You would need {kes(required)} a month, which is {kes(cut)} more than your recent free cash. "
                        "That is only possible by cutting discretionary spending.")
                notes.append(f"Your recent discretionary spending averages {kes(b['discretionary'])} a month.")
            else:
                verdict, head = "no", (f"You would need {kes(required)} a month, more than your free cash "
                                       "plus all your discretionary spending.")
    return _result("Can I afford this purchase?", verdict, head, calcs, assumptions, notes)


# ------------------------------------------------------------------ 2. Saving plan / time to a target
def save_plan(b, today, monthly=None, target=None):
    surplus, current = b["surplus"], b["savings"]
    calcs = [("Average monthly surplus (income − spending)", kes(surplus)),
             ("Of which you already save each month", kes(b["saved"])),
             ("Total saved so far (all goals)", kes(current))]
    assumptions = ["The surplus includes what you already save, so it is the most you could put into savings in total.",
                   "Income and spending are assumed to stay near your recent averages."]
    notes, table = [], None
    verdict, head = "info", ""
    pace = monthly
    if monthly is not None:
        monthly = money(monthly)
        calcs.append(("Monthly saving you asked about", kes(monthly)))
        if surplus >= monthly:
            verdict, head = "good", f"Saving {kes(monthly)} a month fits within your recent surplus of {kes(surplus)}."
        elif surplus + b["discretionary"] >= monthly:
            need = money(monthly - surplus)
            verdict = "tight"
            head = (f"{kes(monthly)} a month is {kes(need)} more than your recent surplus. You would need to cut "
                    "discretionary spending to manage it.")
        else:
            verdict, head = "no", (f"{kes(monthly)} a month is more than your recent surplus plus all your discretionary "
                                   "spending.")
    elif surplus > 0:
        pace = surplus
        notes.append(f"No monthly amount was given, so your recent surplus of {kes(surplus)} was used as the pace.")
    if target is not None:
        target = money(target)
        remaining = money(max(ZERO, target - current))
        calcs += [("Target", kes(target)), ("Still to save", kes(remaining))]
        if remaining == 0:
            verdict, head = "good", "You have already saved at least this much across your goals."
        elif not pace or pace <= 0:
            verdict, head = "no", ("Your recent figures show no surplus, so a completion date cannot be estimated until "
                                   "income rises or spending falls.")
        else:
            n = _ceil_div(remaining, pace)
            if n > MAX_MONTHS_SHOWN:
                notes.append("At this pace the target would take over 50 years, so no date is given.")
            else:
                text = f"At {kes(pace)} a month you would reach {kes(target)} in about {n} months (around {_month_label(today, n)})."
                head = f"{head} {text}".strip() if monthly is not None else text
                calcs.append(("Months to reach the target", str(n)))
            if monthly is None:
                verdict = "info"
            table = {"header": ["Monthly saving", "Months", "Around"], "rows": []}
            for factor in (Decimal("0.5"), Decimal("1"), Decimal("1.5"), Decimal("2")):
                p = money(pace * factor)
                months = _ceil_div(remaining, p) if p > 0 else None
                if months and months <= MAX_MONTHS_SHOWN:
                    table["rows"].append([kes(p), str(months), _month_label(today, months)])
    if not head:
        head = "Enter a monthly amount, a target, or both."
    return _result("Saving plan", verdict, head, calcs, assumptions, notes, table)


# ------------------------------------------------------------------ 3. Cutting a category
def cut_category(b, today, category_name, is_essential, reduction):
    avg_cat = b["category_avg"].get(category_name, ZERO)
    reduction = money(reduction)
    calcs = [("Average monthly spending on this category", kes(avg_cat)), ("Reduction you asked about", kes(reduction))]
    assumptions = ["Your spending in other categories and your income stay the same.",
                   "Average spending uses your recent full months."]
    notes = []
    if avg_cat <= 0:
        return _result("Cutting a category", "info", f"No spending on {category_name} was recorded in your recent full months, "
                       "so there is nothing to reduce.", calcs, assumptions, notes)
    effective = min(reduction, avg_cat)
    if reduction > avg_cat:
        notes.append(f"You cannot save more than you spend, so the reduction was capped at {kes(avg_cat)}.")
    share = an.pct(effective, avg_cat)
    new_surplus = money(b["surplus"] + effective)
    calcs += [("Saving per month", kes(effective)), ("Saving over 12 months", kes(effective * 12)),
              ("That is this share of the category", f"{share}%"), ("Surplus per month: now → after", f"{kes(b['surplus'])} → {kes(new_surplus)}")]
    if share <= GOOD_CUT_MAX_PCT:
        verdict, head = "good", f"Cutting {kes(effective)} a month ({share}% of {category_name}) looks realistic."
    elif share <= TIGHT_CUT_MAX_PCT:
        verdict, head = "tight", f"Cutting {share}% of {category_name} is a big change and may be hard to keep up."
    else:
        verdict, head = "no", f"Cutting more than half of your {category_name} spending is unlikely to last."
    if is_essential:
        notes.append(f"{category_name} is an essential category, so check that a cut will not harm your wellbeing or studies.")
    return _result("Cutting a category", verdict, head, calcs, assumptions, notes)


# ------------------------------------------------------------------ 4. Income changes
def income_change(b, today, direction, mode, value):
    value = Decimal(value)
    old_income = b["income"]
    delta = old_income * value / 100 if mode == "percent" else value
    new_income = money(max(ZERO, old_income + delta if direction == "increase" else old_income - delta))
    new_surplus = money(new_income - b["spent"])
    label = f"{value}%" if mode == "percent" else kes(value)
    calcs = [("Average monthly income now", kes(old_income)), (f"Income after a {label} {direction}", kes(new_income)),
             ("Average monthly spending", kes(b["spent"])), ("Surplus per month: now → after", f"{kes(b['surplus'])} → {kes(new_surplus)}")]
    assumptions = ["Your spending stays at its recent average.", "The change is assumed to last every month."]
    notes = []
    if new_surplus < 0:
        gap = money(-new_surplus)
        verdict, head = "no", f"Spending would exceed income by about {kes(gap)} a month."
        if b["balance"] > 0:
            months = (b["balance"] / gap).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            calcs.append(("Months your available balance could cover the gap", str(months)))
        else:
            notes.append("You have no available balance to cover that gap.")
    elif new_income > 0 and an.pct(new_surplus, new_income) < SURPLUS_COMFORT_PCT:
        verdict, head = "tight", f"You would still break even or have a small surplus ({kes(new_surplus)} a month), leaving little room for savings."
    else:
        verdict, head = "good", f"You would have a surplus of about {kes(new_surplus)} a month."
    return _result("If my income changes", verdict, head, calcs, assumptions, notes)
