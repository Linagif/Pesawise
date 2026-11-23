from datetime import date
from decimal import Decimal as D

from django.urls import reverse

from advisor import simulator as sim
from core.testing import BaseTestCase, cat
from core.utils import add_months, month_range


class SimBase(BaseTestCase):
    """Last full month: income 10,000; Rent 3,000 + Food 1,000 (essential); Entertainment 1,000 (discretionary);
    500 saved. So: surplus 5,000, free 4,500, balance 4,500, essentials 4,000, discretionary 1,000."""

    def past(self, back, day=10):
        y, m = add_months(self.today.year, self.today.month, -back)
        return date(y, m, min(day, month_range(y, m)[1].day))

    def setUp(self):
        super().setUp()
        d = self.past(1)
        self.income(10000, day=d)
        self.expense(3000, category="Rent", day=d); self.expense(1000, category="Food", day=d)
        self.expense(1000, category="Entertainment", day=d)
        self.contribute(self.goal(target=50000), 500, day=d)
        self.b = sim.baseline(self.user, self.today)


class BaselineTests(SimBase):
    def test_baseline_figures(self):
        b = self.b
        self.assertEqual((b["income"], b["spent"], b["surplus"], b["saved"], b["free"]),
                         (D("10000.00"), D("5000.00"), D("5000.00"), D("500.00"), D("4500.00")))
        self.assertEqual((b["essential"], b["discretionary"], b["balance"], b["savings"], b["months_used"]),
                         (D("4000.00"), D("1000.00"), D("4500.00"), D("500.00"), 1))
        self.assertEqual(b["category_avg"]["Food"], D("1000.00"))

    def test_baseline_averages_several_months(self):
        d2 = self.past(2)
        self.income(6000, day=d2); self.expense(3000, category="Rent", day=d2)
        b = sim.baseline(self.user, self.today)
        self.assertEqual((b["months_used"], b["income"], b["spent"]), (2, D("8000.00"), D("4000.00")))
        self.assertEqual((b["surplus_min"], b["surplus_max"]), (D("3000.00"), D("5000.00")))

    def test_baseline_none_without_a_complete_month(self):
        self.client.logout()
        self.expense(100, user=self.other)                                           # current month only
        self.assertIsNone(sim.baseline(self.other, self.today))

    def test_baseline_ignores_other_students_and_current_month(self):
        self.income(99999, user=self.other, day=self.past(1)); self.expense(99999, day=self.today)
        b = sim.baseline(self.user, self.today)
        self.assertEqual((b["income"], b["spent"]), (D("10000.00"), D("5000.00")))


class AffordTests(SimBase):
    def test_pay_now_good_when_buffer_kept(self):
        r = sim.can_afford(self.b, D("400"), self.today)
        self.assertEqual(r["verdict"], "good")

    def test_pay_now_tight_when_buffer_lost(self):
        r = sim.can_afford(self.b, D("2000"), self.today)               # 4,500 - 2,000 = 2,500 < 4,000
        self.assertEqual(r["verdict"], "tight")
        self.assertIn("KSh 2,500.00", r["headline"])

    def test_shortfall_closed_quickly(self):
        r = sim.can_afford(self.b, D("6000"), self.today)               # gap 1,500 / free 4,500 = 1 month
        self.assertEqual(r["verdict"], "tight")
        self.assertIn("about 1 month ", r["headline"])

    def test_laptop_example_is_not_supported(self):
        r = sim.can_afford(self.b, D("60000"), self.today)              # gap 55,500 / 4,500 -> 13 months > 12
        self.assertEqual(r["verdict"], "no")
        self.assertIn("13 months", r["headline"])

    def test_deadline_modes(self):
        self.assertEqual(sim.can_afford(self.b, D("10000"), self.today, 2)["verdict"], "good")    # 2,750/month <= 4,500
        self.assertEqual(sim.can_afford(self.b, D("10000"), self.today, 1)["verdict"], "tight")   # 5,500 <= 4,500+1,000
        self.assertEqual(sim.can_afford(self.b, D("12000"), self.today, 1)["verdict"], "no")      # 7,500 > 5,500
        self.assertEqual(sim.can_afford(self.b, D("1000"), self.today, 1)["verdict"], "good")     # balance covers it

    def test_no_free_cash_cannot_close_gap(self):
        b = dict(self.b, free=D("0.00"))
        r = sim.can_afford(b, D("9000"), self.today)
        self.assertEqual(r["verdict"], "no")
        self.assertIn("no free cash", r["headline"])


class SavePlanTests(SimBase):
    def test_monthly_feasibility(self):
        self.assertEqual(sim.save_plan(self.b, self.today, monthly=D("4000"))["verdict"], "good")
        self.assertEqual(sim.save_plan(self.b, self.today, monthly=D("5500"))["verdict"], "tight")
        self.assertEqual(sim.save_plan(self.b, self.today, monthly=D("8000"))["verdict"], "no")

    def test_time_to_target_and_alternatives(self):
        r = sim.save_plan(self.b, self.today, monthly=D("5000"), target=D("100000"))     # remaining 99,500 / 5,000 = 20
        self.assertIn(("Months to reach the target", "20"), r["calcs"])
        self.assertEqual(len(r["table"]["rows"]), 4)
        self.assertEqual(r["table"]["rows"][1][1], "20")

    def test_target_only_uses_surplus_as_pace(self):
        r = sim.save_plan(self.b, self.today, target=D("10500"))                         # remaining 10,000 / 5,000 = 2
        self.assertEqual(r["verdict"], "info")
        self.assertIn(("Months to reach the target", "2"), r["calcs"])
        self.assertTrue(any("recent surplus" in n for n in r["notes"]))

    def test_no_surplus_gives_no_date(self):
        b = dict(self.b, surplus=D("-200.00"))
        r = sim.save_plan(b, self.today, target=D("5000"))
        self.assertEqual(r["verdict"], "no")
        self.assertNotIn("Months to reach the target", [c[0] for c in r["calcs"]])

    def test_target_already_met(self):
        self.assertEqual(sim.save_plan(self.b, self.today, target=D("300"))["verdict"], "good")


class CutTests(SimBase):
    def test_small_cut_is_realistic(self):
        r = sim.cut_category(self.b, self.today, "Food", True, D("200"))                # 20%
        self.assertEqual(r["verdict"], "good")
        self.assertIn(("Saving over 12 months", "KSh 2,400.00"), r["calcs"])
        self.assertTrue(any("essential" in n for n in r["notes"]))

    def test_bigger_cuts_get_harder_verdicts(self):
        self.assertEqual(sim.cut_category(self.b, self.today, "Food", True, D("400"))["verdict"], "tight")
        self.assertEqual(sim.cut_category(self.b, self.today, "Food", True, D("800"))["verdict"], "no")

    def test_cut_capped_at_what_you_spend(self):
        r = sim.cut_category(self.b, self.today, "Food", True, D("1500"))
        self.assertIn(("Saving per month", "KSh 1,000.00"), r["calcs"])
        self.assertTrue(any("capped" in n for n in r["notes"]))

    def test_category_with_no_spending(self):
        self.assertEqual(sim.cut_category(self.b, self.today, "Shopping", False, D("100"))["verdict"], "info")


class IncomeChangeTests(SimBase):
    def test_twenty_percent_fall(self):
        r = sim.income_change(self.b, self.today, "decrease", "percent", D("20"))        # 8,000 - 5,000 = 3,000
        self.assertEqual(r["verdict"], "good")
        self.assertIn(("Income after a 20% decrease", "KSh 8,000.00"), r["calcs"])

    def test_break_even_is_tight(self):
        self.assertEqual(sim.income_change(self.b, self.today, "decrease", "percent", D("50"))["verdict"], "tight")

    def test_deficit_and_how_long_balance_lasts(self):
        r = sim.income_change(self.b, self.today, "decrease", "percent", D("60"))        # 4,000 - 5,000 = -1,000
        self.assertEqual(r["verdict"], "no")
        self.assertIn(("Months your available balance could cover the gap", "4.5"), r["calcs"])

    def test_increase_by_amount(self):
        r = sim.income_change(self.b, self.today, "increase", "amount", D("5000"))
        self.assertEqual(r["verdict"], "good")
        self.assertIn("KSh 10,000.00", r["headline"])

    def test_cannot_go_below_zero_income(self):
        r = sim.income_change(self.b, self.today, "decrease", "amount", D("99999"))
        self.assertIn(("Income after a KSh 99,999.00 decrease", "KSh 0.00"), r["calcs"])


class SimulatorPageTests(SimBase):
    url = "advisor:simulator"

    def get(self, **params):
        return self.client.get(reverse(self.url), params)

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse(self.url))
        self.assertEqual(r.status_code, 302)

    def test_renders_without_enough_history(self):
        self.client.logout(); self.client.login(username="bob", password=self.PASSWORD)
        r = self.get()
        self.assertContains(r, "needs at least one full past month")

    def test_each_scenario_runs_end_to_end(self):
        cases = [{"scenario": "afford", "price": "60000"},
                 {"scenario": "save", "monthly": "4000", "target": "20000"},
                 {"scenario": "cut", "category": cat("Food").pk, "reduction": "200"},
                 {"scenario": "income", "direction": "decrease", "mode": "percent", "value": "20"}]
        for c in cases:
            r = self.get(**c)
            self.assertEqual(r.status_code, 200, c)
            self.assertIsNotNone(r.context["result"], c)
            self.assertContains(r, "Limitations")
            self.assertContains(r, "not predictions, guarantees")

    def test_invalid_input_shows_errors_and_no_result(self):
        bad = [{"scenario": "afford", "price": "-5"}, {"scenario": "afford", "price": "abc"},
               {"scenario": "afford", "price": "100", "months": "0"}, {"scenario": "save"},
               {"scenario": "income", "direction": "decrease", "mode": "percent", "value": "150"},
               {"scenario": "cut", "category": "9999999", "reduction": "100"},
               {"scenario": "afford", "price": "99999999999999"}, {"scenario": "nonsense"}]
        for params in bad:
            r = self.get(**params)
            self.assertEqual(r.status_code, 200, params)
            self.assertIsNone(r.context["result"], params)

    def test_cannot_simulate_with_another_students_category(self):
        from core.models import Category
        theirs = Category.objects.create(user=self.other, name="BobSecretCat", category_type="EXPENSE")
        r = self.get(scenario="cut", category=theirs.pk, reduction="100")
        self.assertIsNone(r.context["result"])

    def test_simulating_never_changes_data(self):
        from expenses.models import Expense
        before = Expense.objects.count()
        self.get(scenario="afford", price="500")
        self.assertEqual(Expense.objects.count(), before)

    def test_health_page_links_to_simulator(self):
        self.assertContains(self.client.get(reverse("advisor:tips")), "What-if simulator")
