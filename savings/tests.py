from datetime import timedelta
from decimal import Decimal as D

from django.urls import reverse

from core.testing import BaseTestCase
from dashboard import services
from savings.models import SavingsContribution, SavingsGoal


class SavingsTests(BaseTestCase):
    def test_create_goal(self):
        r = self.client.post(reverse("savings:add"), {"name": "Laptop", "target_amount": "10000", "starting_amount": "4000",
                                                       "target_date": (self.today + timedelta(days=30)).isoformat(), "description": ""})
        g = SavingsGoal.objects.get()
        self.assertRedirects(r, reverse("savings:detail", args=[g.pk]))

    def test_progress_example_from_spec(self):
        g = self.goal(target=10000, start=4000)
        self.assertEqual((g.current_amount, g.remaining, g.progress), (D("4000.00"), D("6000.00"), D("40.0")))

    def test_contributions_update_progress_and_history(self):
        g = self.goal(target=1000)
        self.client.post(reverse("savings:detail", args=[g.pk]), {"amount": "250", "contribution_date": self.today.isoformat(), "notes": "week 1"})
        self.assertEqual(SavingsContribution.objects.count(), 1)
        self.assertEqual((g.current_amount, g.progress), (D("250.00"), D("25.0")))

    def test_goal_validation(self):
        bad = [{"target_amount": "0"}, {"starting_amount": "-1"}, {"target_date": (self.today - timedelta(days=1)).isoformat()}]
        for over in bad:
            data = {"name": "X", "target_amount": "100", "starting_amount": "0",
                    "target_date": (self.today + timedelta(days=5)).isoformat(), **over}
            self.assertEqual(self.client.post(reverse("savings:add"), data).status_code, 200, over)
        self.assertEqual(SavingsGoal.objects.count(), 0)

    def test_contribution_validation(self):
        g = self.goal()
        for amount in ("0", "-10"):
            self.client.post(reverse("savings:detail", args=[g.pk]), {"amount": amount, "contribution_date": self.today.isoformat()})
        self.assertEqual(g.contributions.count(), 0)

    def test_savings_not_double_counted(self):
        self.income(5000)
        self.expense(1000)
        g = self.goal(start=2000)                       # starting amount must NOT touch the balance
        self.contribute(g, 500)
        self.assertEqual(services.available_balance(self.user), D("3500.00"))   # 5000 - 1000 - 500
        self.assertEqual(services.total_expenses(self.user), D("1000.00"))      # contribution is not an expense
        self.assertEqual(services.total_savings(self.user), D("2500.00"))

    def test_edit_and_delete_contribution_recalculate(self):
        self.income(1000)
        g = self.goal()
        c = self.contribute(g, 300)
        self.assertEqual(services.available_balance(self.user), D("700.00"))
        self.client.post(reverse("savings:contribution_edit", args=[c.pk]), {"amount": "100", "contribution_date": self.today.isoformat(), "notes": ""})
        self.assertEqual(services.available_balance(self.user), D("900.00"))
        self.client.post(reverse("savings:contribution_delete", args=[c.pk]))
        self.assertEqual(services.available_balance(self.user), D("1000.00"))

    def test_goal_complete_and_progress_capped(self):
        g = self.goal(target=100)
        self.contribute(g, 150)
        self.assertTrue(g.is_complete)
        self.assertEqual((g.progress, g.remaining), (D("100.0"), D("0.00")))

    def test_isolation(self):
        theirs = self.goal(user=self.other)
        self.assertEqual(self.client.get(reverse("savings:detail", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("savings:detail", args=[theirs.pk]), {"amount": "5", "contribution_date": self.today.isoformat()}).status_code, 404)
        self.assertEqual(self.client.post(reverse("savings:delete", args=[theirs.pk])).status_code, 404)
        c = self.contribute(theirs, 10)
        self.assertEqual(self.client.post(reverse("savings:contribution_delete", args=[c.pk])).status_code, 404)
        self.assertEqual(services.total_savings(self.user), D("0.00"))
