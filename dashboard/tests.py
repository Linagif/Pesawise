import json
from datetime import timedelta
from decimal import Decimal as D

from django.urls import reverse

from core.testing import BaseTestCase
from dashboard import services as svc


class CalculationTests(BaseTestCase):
    def test_decimal_precision_no_float_errors(self):
        self.income("0.10"); self.income("0.20")
        self.assertEqual(svc.total_income(self.user), D("0.30"))                    # floats would give 0.30000000000000004
        self.assertIsInstance(svc.total_income(self.user), D)

    def test_zero_data_everywhere(self):
        self.assertEqual(svc.available_balance(self.user), D("0.00"))
        self.assertEqual(svc.daily_summary(self.user, self.today)["highest"], None)
        self.assertEqual(svc.average_daily_spend_before(self.user, self.today), (D("0.00"), 0))
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:reports")).status_code, 200)

    def test_available_balance_formula(self):
        self.income(10000); self.income(2500, source="Casual jobs")
        self.expense(500); self.expense(1500, category="Rent")
        self.contribute(self.goal(), 1000)
        self.assertEqual(svc.available_balance(self.user), D("9500.00"))             # 12500 - 2000 - 1000

    def test_negative_balance_allowed_and_flagged(self):
        self.expense(500)
        self.assertEqual(svc.available_balance(self.user), D("-500.00"))
        r = self.client.get(reverse("dashboard:home"))
        self.assertEqual(r.context["cards"]["balance"], D("-500.00"))

    def test_period_filters_use_correct_dates(self):
        first = self.today.replace(day=1)
        last_month = first - timedelta(days=1)
        self.expense(100, day=first); self.expense(7, day=last_month)
        self.assertEqual(svc.total_expenses(self.user, first, self.today), D("100.00"))
        self.assertEqual(svc.total_expenses(self.user, last_month, last_month), D("7.00"))

    def test_rounding_half_up(self):
        from core.utils import money
        self.assertEqual(money(D("2.675")), D("2.68"))

    def test_week_and_month_ranges(self):
        from datetime import date
        from core.utils import month_range, week_range, add_months
        self.assertEqual(week_range(date(2026, 11, 13)), (date(2026, 11, 9), date(2026, 11, 15)))   # Mon-Sun
        self.assertEqual(month_range(2024, 2), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(add_months(2026, 1, -2), (2025, 11))


class DashboardViewTests(BaseTestCase):
    def test_cards_and_charts_use_actual_records(self):
        self.income(10000)
        self.expense(300, category="Food"); self.expense(200, category="Transport")
        g = self.goal(target=1000, start=100); self.contribute(g, 400)
        self.budget(Food=1000, Transport=500)
        r = self.client.get(reverse("dashboard:home"))
        c = r.context["cards"]
        self.assertEqual((c["income"], c["expenses"], c["balance"], c["savings"]), (D("10000.00"), D("500.00"), D("9100.00"), D("500.00")))
        self.assertEqual((c["budget"], c["budget_remaining"]), (D("1500.00"), D("1000.00")))
        chart = r.context["chart"]
        self.assertEqual(dict(zip(chart["cat_labels"], chart["cat_values"])), {"Food": 300.0, "Transport": 200.0})
        self.assertEqual(chart["income"][-1], 10000.0)
        self.assertEqual(chart["goal_labels"], ["Laptop"])
        self.assertEqual(chart["goal_progress"], [50.0])
        self.assertContains(r, 'id="chart-data"')

    def test_dashboard_only_shows_own_data(self):
        self.income(7777, user=self.other); self.expense(555, user=self.other, desc="BobSecretPurchase")
        self.goal(user=self.other, name="BobGoal")
        self.income(100)
        r = self.client.get(reverse("dashboard:home"))
        self.assertEqual(r.context["cards"]["income"], D("100.00"))
        self.assertNotContains(r, "BobSecretPurchase"); self.assertNotContains(r, "BobGoal")
        data = json.dumps(r.context["chart"])
        self.assertNotIn("BobGoal", data)

    def test_quick_add_button_present_on_dashboard(self):
        r = self.client.get(reverse("dashboard:home"))
        self.assertContains(r, 'id="quickExpense"'); self.assertContains(r, "Record expense")

    def test_all_report_kinds_render_and_use_own_data(self):
        self.income(100); self.expense(40); self.expense(9999, user=self.other)
        for kind in ["daily", "weekly", "monthly", "income", "expense", "savings", "budget"]:
            r = self.client.get(reverse("dashboard:reports"), {"kind": kind})
            self.assertEqual(r.status_code, 200, kind)
            self.assertEqual(r.context["expense_total"], D("40.00"), kind)
        r = self.client.get(reverse("dashboard:reports"), {"kind": "nonsense", "date": "garbage"})
        self.assertEqual(r.status_code, 200)                                      # bad input never crashes

    def test_empty_state_for_new_student(self):
        r = self.client.get(reverse("dashboard:home"))
        self.assertContains(r, "Let's set up your money picture")

    def test_impossible_dates_in_url_do_not_crash(self):
        for url in (reverse("dashboard:reports") + "?kind=daily&date=2020-13-45", reverse("expenses:daily") + "?date=2021-02-31"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_custom_404_page(self):
        r = self.client.get("/definitely/not/here/")
        self.assertEqual(r.status_code, 404)


class ExportTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.income(10000)
        self.expense(250.50, desc="Lunch at campus")
        self.expense(100, desc="=HYPERLINK(\"http://evil.example\")")        # a formula-injection attempt
        self.expense(9999, user=self.other, desc="BobSecretPurchase")

    def csv(self, **params):
        return self.client.get(reverse("dashboard:report_csv"), {"kind": "expense", **params})

    def test_csv_download_headers_and_content(self):
        r = self.csv()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment; filename=", r["Content-Disposition"])
        self.assertIn(".csv", r["Content-Disposition"])
        text = r.content.decode("utf-8-sig")
        self.assertIn("Lunch at campus", text)
        self.assertIn("250.50", text)                      # plain number, 2 d.p., no currency text
        self.assertIn("Expenses,350.50", text)             # summary total
        self.assertNotIn("BobSecretPurchase", text)        # data isolation

    def test_csv_neutralises_formula_injection(self):
        text = self.csv().content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", text)
        self.assertNotIn(",=HYPERLINK", text)

    def test_csv_for_every_report_kind(self):
        for kind in ["daily", "weekly", "monthly", "income", "expense", "savings", "budget"]:
            r = self.client.get(reverse("dashboard:report_csv"), {"kind": kind})
            self.assertEqual(r.status_code, 200, kind)

    def test_pdf_is_a_real_pdf_for_every_kind(self):
        for kind in ["daily", "weekly", "monthly", "income", "expense", "savings", "budget"]:
            r = self.client.get(reverse("dashboard:report_pdf"), {"kind": kind})
            self.assertEqual(r.status_code, 200, kind)
            self.assertEqual(r["Content-Type"], "application/pdf")
            self.assertTrue(r.content.startswith(b"%PDF"), kind)

    def test_pdf_survives_special_characters(self):
        self.expense(5, desc="<b>Tea & <i>mandazi</i></b> & 'quotes'")
        r = self.client.get(reverse("dashboard:report_pdf"), {"kind": "expense"})
        self.assertEqual(r.status_code, 200)

    def test_export_respects_period_and_bad_input(self):
        r = self.client.get(reverse("dashboard:report_csv"), {"kind": "expense", "start": "garbage", "end": "2020-13-45"})
        self.assertEqual(r.status_code, 200)

    def test_exports_require_login(self):
        self.client.logout()
        for name in ("dashboard:report_csv", "dashboard:report_pdf"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn("/accounts/login/", r["Location"])

    def test_report_page_has_download_buttons_keeping_filters(self):
        r = self.client.get(reverse("dashboard:reports"), {"kind": "expense"})
        self.assertContains(r, "Download CSV")
        self.assertContains(r, "export/pdf/?kind=expense")
