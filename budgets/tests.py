from decimal import Decimal as D

from django.urls import reverse

from budgets.models import Budget, BudgetAllocation
from core.testing import BaseTestCase, cat
from dashboard import services


class BudgetTests(BaseTestCase):
    def test_create_budget_and_prevent_duplicate_month(self):
        data = {"month": self.today.month, "year": self.today.year}
        self.client.post(reverse("budgets:create"), data)
        self.assertEqual(Budget.objects.count(), 1)
        r = self.client.post(reverse("budgets:create"), data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Budget.objects.count(), 1)

    def test_allocations_total_example_from_spec(self):
        b = self.budget(Rent=3000, Food=2500, Transport=1500, Internet_and_airtime=500, Entertainment=500, Savings=1000,
                        Miscellaneous=1000)
        self.assertEqual(b.total_amount, D("10000.00"))

    def test_add_edit_delete_allocation(self):
        b = Budget.objects.create(user=self.user, month=self.today.month, year=self.today.year)
        self.client.post(reverse("budgets:detail", args=[b.pk]), {"category": cat("Food").pk, "allocated_amount": "2500"})
        a = BudgetAllocation.objects.get()
        self.client.post(reverse("budgets:allocation_edit", args=[a.pk]), {"allocated_amount": "3000"})
        a.refresh_from_db(); self.assertEqual(a.allocated_amount, D("3000.00"))
        self.client.post(reverse("budgets:allocation_delete", args=[a.pk]))
        self.assertEqual(BudgetAllocation.objects.count(), 0)

    def test_same_category_cannot_be_allocated_twice_or_negative(self):
        b = self.budget(Food=100)
        self.client.post(reverse("budgets:detail", args=[b.pk]), {"category": cat("Food").pk, "allocated_amount": "50"})
        self.client.post(reverse("budgets:detail", args=[b.pk]), {"category": cat("Rent").pk, "allocated_amount": "-5"})
        self.assertEqual(b.allocations.count(), 1)

    def test_remaining_and_utilization_example_from_spec(self):
        b = self.budget(Food=2500)
        self.expense(1800)
        row = services.budget_progress(b)["rows"][0]
        self.assertEqual((row["actual"], row["remaining"], row["pct"], row["status"]), (D("1800.00"), D("700.00"), D("72.0"), "ok"))

    def test_status_thresholds_and_overspend_detection(self):
        b = self.budget(Food=1000)
        self.expense(850)
        self.assertEqual(services.budget_progress(b)["rows"][0]["status"], "warning")
        self.expense(300)
        p = services.budget_progress(b)
        self.assertEqual(p["rows"][0]["status"], "over")
        self.assertEqual(p["remaining"], D("-150.00"))
        self.assertEqual(p["status"], "over")

    def test_zero_budget_is_safe(self):
        self.assertEqual(services.utilization(D("0"), D("0")), D("0.0"))
        self.assertIsNone(services.utilization(D("50"), D("0")))
        b = self.budget(Food=0)
        self.expense(50)
        self.assertEqual(services.budget_progress(b)["rows"][0]["status"], "over")
        self.client.get(reverse("budgets:detail", args=[b.pk]))               # renders without ZeroDivisionError

    def test_unbudgeted_spending_counts_against_total(self):
        b = self.budget(Food=1000)
        self.expense(300, category="Transport")
        p = services.budget_progress(b)
        self.assertEqual((p["unbudgeted"], p["total_actual"], p["remaining"]), (D("300.00"), D("300.00"), D("700.00")))

    def test_savings_line_uses_contributions_not_expenses(self):
        b = self.budget(Savings=1000, Food=500)
        self.contribute(self.goal(), 400)
        row = [r for r in services.budget_progress(b)["rows"] if r["name"] == "Savings"][0]
        self.assertEqual(row["actual"], D("400.00"))

    def test_copy_previous_budget(self):
        from datetime import date
        old = Budget.objects.create(user=self.user, month=1, year=2020)
        BudgetAllocation.objects.create(budget=old, category=cat("Food"), allocated_amount=D("1200"))
        self.client.post(reverse("budgets:create"), {"month": 2, "year": 2020, "copy_previous": "on"})
        new = Budget.objects.get(month=2, year=2020)
        self.assertEqual(new.allocations.get().allocated_amount, D("1200.00"))

    def test_isolation(self):
        theirs = self.budget(user=self.other, Food=100)
        self.assertEqual(self.client.get(reverse("budgets:detail", args=[theirs.pk])).status_code, 404)
        a = theirs.allocations.first()
        self.assertEqual(self.client.post(reverse("budgets:allocation_delete", args=[a.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("budgets:delete", args=[theirs.pk])).status_code, 404)
