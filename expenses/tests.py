from datetime import timedelta
from decimal import Decimal as D

from django.contrib.messages import get_messages
from django.urls import reverse

from core.testing import BaseTestCase, cat
from dashboard import services
from expenses.models import Expense


class ExpenseTests(BaseTestCase):
    def payload(self, **over):
        data = {"amount": "200", "description": "Lunch", "category": cat("Food").pk, "expense_date": self.today.isoformat(),
                "payment_method": "MPESA", "is_planned": "True", "notes": ""}
        data.update(over)
        return data

    def test_add_expense_and_balance_updates_automatically(self):
        self.income(5000)
        self.client.post(reverse("expenses:add"), self.payload())
        self.assertEqual(Expense.objects.get().amount, D("200.00"))
        self.assertEqual(services.available_balance(self.user), D("4800.00"))

    def test_multiple_expenses_same_day_and_daily_total(self):
        for desc, cat_name, amt in [("Lunch", "Food", 200), ("Fare", "Transport", 100), ("Airtime", "Internet and airtime", 50),
                                    ("Snacks", "Food", 100), ("Printing", "Education and academic materials", 50)]:
            self.client.post(reverse("expenses:add"), self.payload(description=desc, amount=amt, category=cat(cat_name).pk))
        s = services.daily_summary(self.user, self.today)
        self.assertEqual((s["total"], s["count"], s["highest"].amount), (D("500.00"), 5, D("200.00")))
        self.assertEqual({c["name"]: c["total"] for c in s["by_category"]}["Food"], D("300.00"))

    def test_date_defaults_to_today_and_other_dates_allowed(self):
        r = self.client.get(reverse("expenses:add"))
        self.assertEqual(r.context["form"].fields["expense_date"].initial, self.today)
        self.client.post(reverse("expenses:add"), self.payload(expense_date=(self.today - timedelta(days=3)).isoformat()))
        self.assertEqual(Expense.objects.get().expense_date, self.today - timedelta(days=3))

    def test_validation_blocks_bad_data(self):
        for bad in ({"amount": "0"}, {"amount": "-20"}, {"amount": "abc"}, {"description": ""},
                    {"expense_date": (self.today + timedelta(days=2)).isoformat()}, {"category": cat("Savings", "SAVINGS").pk}):
            self.assertEqual(self.client.post(reverse("expenses:add"), self.payload(**bad)).status_code, 200, bad)
        self.assertEqual(Expense.objects.count(), 0)

    def test_duplicate_submission_blocked_but_different_expense_allowed(self):
        self.client.post(reverse("expenses:add"), self.payload())
        self.client.post(reverse("expenses:add"), self.payload())            # double click
        self.assertEqual(Expense.objects.count(), 1)
        self.client.post(reverse("expenses:add"), self.payload(amount="201"))
        self.assertEqual(Expense.objects.count(), 2)

    def test_edit_and_delete(self):
        e = self.expense(200)
        self.client.post(reverse("expenses:edit", args=[e.pk]), self.payload(amount="350", description="Big lunch"))
        e.refresh_from_db()
        self.assertEqual((e.amount, e.description), (D("350.00"), "Big lunch"))
        self.assertEqual(self.client.get(reverse("expenses:delete", args=[e.pk])).status_code, 200)
        self.assertEqual(Expense.objects.count(), 1)
        self.client.post(reverse("expenses:delete", args=[e.pk]))
        self.assertEqual(Expense.objects.count(), 0)

    def test_weekly_and_monthly_totals(self):
        monday = self.today - timedelta(days=self.today.weekday())
        self.expense(100, day=monday)
        self.expense(50, day=monday + timedelta(days=1)) if monday + timedelta(days=1) <= self.today else self.expense(50, day=monday)
        old = self.today.replace(day=1) - timedelta(days=1)                   # last month
        self.expense(999, day=old)
        t = services.spend_totals(self.user, self.today)
        self.assertEqual(t["week"], D("150.00"))
        self.assertEqual(t["month"], services.total_expenses(self.user, self.today.replace(day=1), self.today))
        self.assertNotIn(D("999.00"), [t["month"]])

    def test_filters_and_search(self):
        self.expense(100, desc="Matatu to town", category="Transport")
        self.expense(200, desc="Chips", category="Food", planned=False)
        r = self.client.get(reverse("expenses:list"), {"q": "matatu"})
        self.assertEqual(r.context["filtered_total"], D("100.00"))
        r = self.client.get(reverse("expenses:list"), {"category": cat("Food").pk})
        self.assertEqual(r.context["filtered_total"], D("200.00"))
        r = self.client.get(reverse("expenses:list"), {"planned": "0"})
        self.assertEqual(r.context["filtered_total"], D("200.00"))

    def test_daily_view_previous_day(self):
        y = self.today - timedelta(days=1)
        self.expense(80, day=y)
        r = self.client.get(reverse("expenses:daily"), {"date": y.isoformat()})
        self.assertEqual(r.context["summary"]["total"], D("80.00"))
        r = self.client.get(reverse("expenses:daily"), {"date": (self.today + timedelta(days=5)).isoformat()})
        self.assertEqual(r.context["day"], self.today)                        # future clamps to today

    def test_overspending_is_recorded_and_flagged(self):
        self.budget(Food=500)
        r = self.client.post(reverse("expenses:add"), self.payload(amount="700"), follow=True)
        self.assertEqual(Expense.objects.get().amount, D("700.00"))           # still saved
        texts = [str(m) for m in r.context["messages"]]
        self.assertTrue(any("Over budget" in t for t in texts), texts)        # and clearly flagged
        self.assertEqual(services.category_budget_alert(self.user, cat("Food"), self.today)[0], "danger")

    def test_isolation(self):
        theirs = self.expense(300, user=self.other)
        self.assertEqual(self.client.get(reverse("expenses:edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("expenses:delete", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("expenses:list")).context["filtered_total"], D("0.00"))
        self.assertEqual(services.total_expenses(self.user), D("0.00"))

    def test_custom_category_usable_and_private(self):
        from core.models import Category
        mine = Category.objects.create(user=self.user, name="Pets", category_type="EXPENSE")
        self.client.post(reverse("expenses:add"), self.payload(category=mine.pk))
        self.assertEqual(Expense.objects.count(), 1)
        self.client.logout(); self.client.login(username="bob", password=self.PASSWORD)
        self.assertEqual(self.client.post(reverse("expenses:add"), self.payload(category=mine.pk)).status_code, 200)

    def test_unsafe_next_redirect_ignored(self):
        r = self.client.post(reverse("expenses:add"), {**self.payload(), "next": "https://evil.example/"})
        self.assertRedirects(r, reverse("expenses:daily"))
