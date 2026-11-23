from datetime import date, timedelta

from django.urls import reverse

from advisor.rules import generate_tips
from core.testing import BaseTestCase


class AdvisorTests(BaseTestCase):
    def texts(self, today=None):
        return " ".join(t["title"] + " " + t["text"] for t in generate_tips(self.user, today or self.today))

    def test_no_data_gives_getting_started_only(self):
        tips = generate_tips(self.user, self.today)
        self.assertEqual(len(tips), 1)
        self.assertIn("first expense", tips[0]["text"])

    def test_prompts_for_budget_when_none(self):
        self.expense(100)
        self.assertIn("no budget", self.texts())

    def test_overspend_and_near_limit_rules(self):
        self.budget(Food=1000, Transport=1000)
        self.expense(850, category="Food"); self.expense(1200, category="Transport")
        t = self.texts()
        self.assertIn("used 85.0% of your Food budget", t)
        self.assertIn("gone over your Transport budget", t)

    def test_no_average_tip_without_enough_history(self):
        base = self.today.replace(day=1)
        if self.today.day < 8:
            self.skipTest("needs a few days earlier in the month")
        self.expense(100, day=base); self.expense(900)
        self.assertNotIn("Higher than usual", self.texts())          # only 1 earlier day -> not enough data

    def test_above_average_tip_with_enough_history(self):
        today = date(self.today.year, self.today.month, 1) + timedelta(days=9)   # the 10th: 9 earlier days available
        if today > self.today:
            self.skipTest("future date")
        for i in range(6):
            self.expense(100, day=today.replace(day=1) + timedelta(days=i))
        self.expense(800, day=today)
        self.assertIn("Higher than usual", self.texts(today))

    def test_unplanned_purchases_rule(self):
        for _ in range(3):
            self.expense(50, planned=False)
        self.assertIn("unplanned purchases", self.texts())

    def test_savings_progress_tip(self):
        self.expense(10)
        g = self.goal(target=1000); self.contribute(g, 300)
        self.assertIn("30.0% of the way", self.texts())

    def test_tips_only_from_own_data_and_page_renders(self):
        self.expense(100, user=self.other); self.budget(user=self.other, Food=10)
        self.assertEqual(len(generate_tips(self.user, self.today)), 1)
        r = self.client.get(reverse("advisor:tips"))
        self.assertContains(r, "not from a professional financial adviser")
