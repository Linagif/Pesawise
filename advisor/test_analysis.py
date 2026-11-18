from datetime import date
from decimal import Decimal as D

from django.urls import reverse

from advisor import analysis as an
from core.models import Category
from core.testing import BaseTestCase, cat
from core.utils import add_months, month_range


class AnalysisBase(BaseTestCase):
    def past(self, back, day=10):
        """A date `back` calendar months before today (day clamped to the month length)."""
        y, m = add_months(self.today.year, self.today.month, -back)
        return date(y, m, min(day, month_range(y, m)[1].day))


class HelperTests(AnalysisBase):
    def test_pct_rounding_and_zero_whole(self):
        self.assertEqual(an.pct(D("1"), D("3")), D("33.3"))
        self.assertEqual(an.pct(D("2"), D("3")), D("66.7"))
        self.assertIsNone(an.pct(D("5"), D("0")))

    def test_default_categories_are_classified(self):
        self.assertEqual(cat("Rent").spending_type, Category.ESSENTIAL)
        self.assertEqual(cat("Food").spending_type, Category.ESSENTIAL)
        self.assertEqual(cat("Entertainment").spending_type, Category.DISCRETIONARY)
        self.assertEqual(cat("Shopping").spending_type, Category.DISCRETIONARY)

    def test_custom_category_defaults_to_discretionary_and_can_be_essential(self):
        self.client.post(reverse("core:add"), {"name": "Medication", "category_type": "EXPENSE", "spending_type": "ESSENTIAL"})
        self.assertEqual(Category.objects.get(user=self.user, name="Medication").spending_type, Category.ESSENTIAL)


class CashFlowTests(AnalysisBase):
    def test_net_cash_flow_and_savings_rate(self):
        self.income(10000); self.expense(4000)
        self.contribute(self.goal(), 1000)
        f = an.cash_flow(self.user, self.today.replace(day=1), self.today)
        self.assertEqual((f["income"], f["expenses"], f["saved"], f["net"]), (D("10000.00"), D("4000.00"), D("1000.00"), D("6000.00")))
        self.assertEqual(f["savings_rate"], D("10.0"))

    def test_no_income_means_no_savings_rate(self):
        self.expense(500)
        f = an.cash_flow(self.user, self.today.replace(day=1), self.today)
        self.assertIsNone(f["savings_rate"])
        self.assertEqual(f["net"], D("-500.00"))

    def test_isolated_from_other_students(self):
        self.income(99999, user=self.other); self.expense(5000, user=self.other)
        f = an.cash_flow(self.user, self.today.replace(day=1), self.today)
        self.assertEqual((f["income"], f["expenses"]), (D("0.00"), D("0.00")))


class SplitTests(AnalysisBase):
    def test_essential_vs_discretionary_shares(self):
        self.income(1000)
        self.expense(300, category="Food"); self.expense(100, category="Entertainment")
        s = an.essential_split(self.user, self.today.replace(day=1), self.today, D("1000"))
        self.assertEqual((s["essential"], s["discretionary"], s["total"]), (D("300.00"), D("100.00"), D("400.00")))
        self.assertEqual((s["essential_share"], s["discretionary_share"], s["essential_pct_of_income"]),
                         (D("75.0"), D("25.0"), D("30.0")))

    def test_no_spending_gives_no_shares(self):
        s = an.essential_split(self.user, self.today.replace(day=1), self.today)
        self.assertIsNone(s["essential_share"])


class EmergencyFundTests(AnalysisBase):
    def test_none_without_a_complete_month_of_essentials(self):
        self.expense(500, category="Food")                       # current month only
        self.assertIsNone(an.emergency_fund(self.user, self.today))

    def test_months_of_cover(self):
        self.expense(3000, category="Rent", day=self.past(1)); self.expense(1000, category="Food", day=self.past(1))
        self.goal(start=8000)
        r = an.emergency_fund(self.user, self.today)
        self.assertEqual((r["avg_essential"], r["months"], r["months_used"]), (D("4000.00"), D("2.0"), 1))

    def test_average_over_several_months_and_discretionary_ignored(self):
        self.expense(4000, category="Rent", day=self.past(1)); self.expense(2000, category="Rent", day=self.past(2))
        self.expense(9999, category="Entertainment", day=self.past(1))
        self.goal(start=6000)
        r = an.emergency_fund(self.user, self.today)
        self.assertEqual((r["avg_essential"], r["months"], r["months_used"]), (D("3000.00"), D("2.0"), 2))

    def test_zero_savings_is_zero_months(self):
        self.expense(2000, category="Rent", day=self.past(1))
        self.assertEqual(an.emergency_fund(self.user, self.today)["months"], D("0.0"))


class CategoryChangeTests(AnalysisBase):
    def test_needs_two_full_months(self):
        self.expense(500, day=self.past(1))
        self.assertFalse(an.category_changes(self.user, self.today)["available"])

    def test_flags_large_rise_with_exact_figures(self):
        self.expense(5000, day=self.past(2)); self.expense(7000, day=self.past(1))
        r = an.category_changes(self.user, self.today)
        row = r["rows"][0]
        self.assertEqual((row["category"], row["pct"], row["direction"], row["before"], row["after"]),
                         ("Food", D("40.0"), "up", D("5000.00"), D("7000.00")))

    def test_ignores_small_percent_and_small_amount_changes(self):
        self.expense(5000, day=self.past(2)); self.expense(5100, day=self.past(1))                      # +2%
        self.expense(100, category="Shopping", day=self.past(2)); self.expense(150, category="Shopping", day=self.past(1))  # +50% but KSh 50
        self.assertEqual(an.category_changes(self.user, self.today)["rows"], [])

    def test_new_and_falling_categories(self):
        self.expense(4000, day=self.past(2)); self.expense(2000, day=self.past(1))                      # fell 50%
        self.expense(1000, category="Entertainment", day=self.past(1))                                  # new
        rows = {r["category"]: r for r in an.category_changes(self.user, self.today)["rows"]}
        self.assertEqual(rows["Food"]["direction"], "down")
        self.assertTrue(rows["Entertainment"]["is_new"])

    def test_current_partial_month_is_never_compared(self):
        self.expense(5000, day=self.past(2)); self.expense(5000, day=self.past(1))
        self.expense(99999, day=self.today)
        self.assertEqual(an.category_changes(self.user, self.today)["rows"], [])


class SmallPurchaseTests(AnalysisBase):
    def test_fires_at_threshold_and_reports_facts(self):
        for i in range(8):
            self.expense(50, desc=f"Snack {i}")
        self.expense(2000, desc="Big")
        r = an.small_purchases(self.user, self.today)
        self.assertTrue(r["fired"])
        self.assertEqual((r["count"], r["total"]), (8, D("400.00")))
        self.assertEqual(r["share"], D("16.7"))

    def test_does_not_fire_below_threshold(self):
        for i in range(7):
            self.expense(50)
        self.assertFalse(an.small_purchases(self.user, self.today)["fired"])


class RecurringTests(AnalysisBase):
    def test_detects_monthly_subscription(self):
        for back in (0, 1, 2):
            self.expense(1100, category="Entertainment", desc="Netflix ", day=self.past(back, 1))
        r = an.recurring_payments(self.user, self.today)
        self.assertEqual((r[0]["description"].strip(), r[0]["typical"], r[0]["months_seen"]), ("Netflix", D("1100.00"), 3))

    def test_two_months_is_not_enough(self):
        for back in (1, 2):
            self.expense(1100, category="Entertainment", desc="Netflix", day=self.past(back, 1))
        self.assertEqual(an.recurring_payments(self.user, self.today), [])

    def test_varying_amounts_are_not_recurring(self):
        for back, amt in ((0, 100), (1, 900), (2, 300)):
            self.expense(amt, desc="Lunch", day=self.past(back, 1))
        self.assertEqual(an.recurring_payments(self.user, self.today), [])

    def test_frequent_daily_purchases_are_not_flagged(self):
        for back in (0, 1, 2):
            for d in (1, 2, 3, 4, 5):
                self.expense(100, desc="Lunch", day=self.past(back, d))
        self.assertEqual(an.recurring_payments(self.user, self.today), [])


class HealthReportTests(AnalysisBase):
    def test_empty_account_has_no_numbers_and_a_notice(self):
        rep = an.build_health_report(self.user, self.today)
        self.assertTrue(all(not i["available"] for i in rep["indicators"]))
        self.assertTrue(rep["notices"])
        self.assertEqual(rep["insights"], [])

    def test_negative_cash_flow_is_flagged(self):
        self.income(1000); self.expense(1500)
        flow = [i for i in an.build_health_report(self.user, self.today)["indicators"] if i["key"] == "cashflow"][0]
        self.assertEqual(flow["status"], "concern")
        self.assertIn("KSh -500.00", flow["value"])

    def test_savings_rate_statuses(self):
        self.income(10000); self.contribute(self.goal(), 1500)
        rate = [i for i in an.build_health_report(self.user, self.today)["indicators"] if i["key"] == "savings_rate"][0]
        self.assertEqual((rate["value"], rate["status"]), ("15.0%", "good"))

    def test_insight_text_contains_real_figures(self):
        self.expense(5000, day=self.past(2)); self.expense(7000, day=self.past(1))
        text = " ".join(i["text"] for i in an.build_health_report(self.user, self.today)["insights"])
        self.assertIn("rose 40.0%", text)
        self.assertIn("KSh 5,000.00", text); self.assertIn("KSh 7,000.00", text)

    def test_last_month_period(self):
        self.income(2000, day=self.past(1)); self.expense(500, day=self.past(1))
        rep = an.build_health_report(self.user, self.today, "last")
        self.assertEqual(rep["flow"]["net"], D("1500.00"))

    def test_report_never_includes_other_students_data(self):
        self.expense(9000, user=self.other, desc="BobSecret", day=self.past(1))
        self.expense(9000, user=self.other, desc="BobSecret", day=self.past(2))
        rep = an.build_health_report(self.user, self.today)
        self.assertEqual(rep["insights"], [])
        self.assertEqual(rep["expense_count"], 0)


class HealthPageTests(AnalysisBase):
    def test_page_renders_both_periods_with_disclaimer(self):
        self.income(5000); self.expense(1000)
        for q in ("", "?period=this", "?period=last", "?period=garbage"):
            r = self.client.get(reverse("advisor:tips") + q)
            self.assertEqual(r.status_code, 200, q)
        self.assertContains(r, "not from a professional financial adviser")
        self.assertContains(r, "Net cash flow")

    def test_page_shows_alerts_section_and_requires_login(self):
        self.assertContains(self.client.get(reverse("advisor:tips")), "Alerts and tips")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("advisor:tips")).status_code, 302)
