from datetime import timedelta
from decimal import Decimal as D

from django.urls import reverse

from core.models import Category
from core.testing import BaseTestCase, cat
from dashboard import services
from income.models import Income


class IncomeTests(BaseTestCase):
    def post_income(self, **over):
        data = {"source": cat("Parents or guardians", Category.INCOME).pk, "amount": "5000", "date_received": self.today.isoformat(),
                "description": "Allowance", "notes": ""}
        data.update(over)
        return self.client.post(reverse("income:add"), data)

    def test_add_income(self):
        self.assertRedirects(self.post_income(), reverse("income:list"))
        self.assertEqual(Income.objects.get().user, self.user)

    def test_irregular_income_and_total_only_counts_recorded(self):
        self.income(5000, day=self.today - timedelta(days=20))
        self.income(1250.50, source="Casual jobs")
        self.assertEqual(services.total_income(self.user), D("6250.50"))

    def test_rejects_zero_negative_and_future_dates(self):
        for bad in ({"amount": "0"}, {"amount": "-5"}, {"date_received": (self.today + timedelta(days=1)).isoformat()}):
            self.assertEqual(self.post_income(**bad).status_code, 200)
        self.assertEqual(Income.objects.count(), 0)

    def test_cannot_use_expense_category_as_income_source(self):
        self.assertEqual(self.post_income(source=cat("Food").pk).status_code, 200)
        self.assertEqual(Income.objects.count(), 0)

    def test_edit_income(self):
        i = self.income(1000)
        self.client.post(reverse("income:edit", args=[i.pk]), {
            "source": i.source_id, "amount": "1500", "date_received": self.today.isoformat(), "description": "Fixed", "notes": ""})
        i.refresh_from_db()
        self.assertEqual(i.amount, D("1500.00"))

    def test_delete_requires_confirmation_then_removes(self):
        i = self.income(1000)
        self.assertEqual(self.client.get(reverse("income:delete", args=[i.pk])).status_code, 200)   # confirm page
        self.assertEqual(Income.objects.count(), 1)
        self.client.post(reverse("income:delete", args=[i.pk]))
        self.assertEqual(Income.objects.count(), 0)

    def test_filter_by_source_and_date(self):
        self.income(100, source="Casual jobs", day=self.today - timedelta(days=30))
        self.income(200, source="Tutoring")
        src = cat("Tutoring", Category.INCOME).pk
        r = self.client.get(reverse("income:list"), {"source": src})
        self.assertEqual(r.context["filtered_total"], D("200.00"))
        r = self.client.get(reverse("income:list"), {"start": (self.today - timedelta(days=5)).isoformat()})
        self.assertEqual(r.context["filtered_total"], D("200.00"))

    def test_custom_income_source(self):
        self.client.post(reverse("core:add"), {"name": "Hustle", "category_type": Category.INCOME})
        self.assertTrue(Category.objects.filter(user=self.user, name="Hustle").exists())

    def test_isolation(self):
        theirs = self.income(999, user=self.other)
        self.assertEqual(self.client.get(reverse("income:edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("income:delete", args=[theirs.pk])).status_code, 404)
        self.assertTrue(Income.objects.filter(pk=theirs.pk).exists())
        r = self.client.get(reverse("income:list"))
        self.assertEqual(r.context["all_time_total"], D("0.00"))
