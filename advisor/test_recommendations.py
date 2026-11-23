from datetime import date, timedelta
from decimal import Decimal as D

from django.urls import reverse
from django.utils import timezone

from advisor import recommendations as rec_engine
from advisor.models import Recommendation
from core.testing import BaseTestCase, cat
from core.utils import add_months, month_range


class RecBase(BaseTestCase):
    def past(self, back, day=10):
        y, m = add_months(self.today.year, self.today.month, -back)
        return date(y, m, min(day, month_range(y, m)[1].day))

    def healthy_month(self, back=1, saved=500):
        """income 10,000; Rent 3,000 + Food 1,000 essential; Entertainment 1,000; `saved` saved.
        -> surplus 5,000, essentials 4,000."""
        d = self.past(back)
        self.income(10000, day=d)
        self.expense(3000, category="Rent", day=d); self.expense(1000, category="Food", day=d)
        self.expense(1000, category="Entertainment", day=d)
        if saved:
            self.contribute(self.goal(target=50000, name=f"G{back}"), saved, day=d)

    def by_key(self, user=None):
        rec_engine.refresh_recommendations(user or self.user, self.today)
        return {r.key: r for r in Recommendation.objects.filter(user=user or self.user)}

    def candidates(self):
        return {c["key"]: c for c in rec_engine.build_candidates(self.user, self.today)}


class RuleTests(RecBase):
    def test_nothing_without_a_full_month_of_history(self):
        self.expense(500); self.income(1000)                          # current month only
        self.assertEqual(rec_engine.build_candidates(self.user, self.today), [])

    def test_emergency_fund_recommendation_figures(self):
        self.healthy_month()
        c = self.candidates()["emergency_fund"]
        self.assertEqual(c["priority"], Recommendation.HIGH)           # under 1 month of cover
        self.assertEqual(c["suggested_amount"], D("2250"))             # half of 4,500 free cash
        self.assertIn("about 2 months", c["estimated_impact"])         # (4,000 - 500) / 2,250 -> 2
        self.assertIn("KSh 500.00 saved", c["evidence"])

    def test_never_suggests_more_than_half_of_free_cash(self):
        self.healthy_month()
        for c in rec_engine.build_candidates(self.user, self.today):
            if c["key"] in ("emergency_fund", "savings_rate"):
                self.assertLessEqual(c["suggested_amount"], D("4500") * D("0.5"))

    def test_no_savings_suggestion_when_there_is_no_free_cash(self):
        d = self.past(1)
        self.income(3000, day=d); self.expense(2990, category="Rent", day=d)          # free cash KSh 10
        keys = self.candidates().keys()
        self.assertNotIn("emergency_fund", keys); self.assertNotIn("savings_rate", keys)

    def test_negative_cashflow_recommendation(self):
        d = self.past(1)
        self.income(3000, day=d); self.expense(3000, category="Rent", day=d); self.expense(1000, category="Entertainment", day=d)
        c = self.candidates()["negative_cashflow"]
        self.assertEqual((c["priority"], c["suggested_amount"]), (Recommendation.HIGH, D("500")))
        self.assertIn("KSh 1,000.00", c["evidence"]); self.assertIn("Entertainment", c["action"])
        self.assertNotIn("Rent", c["action"].split("Start with")[1].split(":")[0])   # never tells you to cut essentials

    def test_negative_cashflow_without_discretionary_spending_has_no_amount(self):
        d = self.past(1)
        self.income(2000, day=d); self.expense(3000, category="Rent", day=d)
        c = self.candidates()["negative_cashflow"]
        self.assertIsNone(c["suggested_amount"])

    def test_category_rise_discretionary_has_amount_essential_does_not(self):
        a, b = self.past(2), self.past(1)
        self.income(10000, day=a); self.income(10000, day=b)
        self.expense(500, category="Entertainment", day=a); self.expense(1500, category="Entertainment", day=b)
        self.expense(1000, category="Food", day=a); self.expense(2000, category="Food", day=b)
        c = self.candidates()
        ent, food = c["category_rise:Entertainment"], c["category_rise:Food"]
        self.assertEqual(ent["suggested_amount"], D("1000"))
        self.assertEqual(ent["baseline_monthly"], D("1500.00"))
        self.assertIsNone(food["suggested_amount"])
        self.assertIn("essential category", food["action"])
        self.assertEqual(food["priority"], Recommendation.LOW)

    def test_savings_rate_recommendation_when_no_essential_history(self):
        d = self.past(1)
        self.income(10000, day=d); self.expense(1000, category="Entertainment", day=d)
        c = self.candidates()
        self.assertNotIn("emergency_fund", c)
        self.assertEqual(c["savings_rate"]["suggested_amount"], D("1000"))        # 10% of income, within half of free cash

    def test_no_savings_rate_recommendation_when_already_saving_enough(self):
        d = self.past(1)
        self.income(10000, day=d); self.expense(1000, category="Entertainment", day=d)
        self.contribute(self.goal(), 1000, day=d)
        self.assertNotIn("savings_rate", self.candidates())

    def test_small_purchase_weekly_limit(self):
        self.healthy_month()
        for i in range(10):
            self.expense(90, desc=f"snack {i}")
        c = self.candidates()["small_purchases"]
        self.assertEqual(c["suggested_amount"], D("150"))                          # 900/30*7 = 210; 80% = 168 -> 150
        self.assertEqual(c["priority"], Recommendation.LOW)

    def test_recurring_payment_recommendation(self):
        for back in (0, 1, 2):
            self.expense(1100, category="Entertainment", desc="Netflix", day=self.past(back, 1))
        c = self.candidates()
        key = "recurring:netflix"
        self.assertEqual(c[key]["suggested_amount"], D("1100.00"))
        self.assertIn("confirm", c[key]["confidence_note"].lower())

    def test_essential_recurring_payments_never_get_a_stop_it_recommendation(self):
        for back in (0, 1, 2):
            self.expense(3000, category="Rent", desc="Rent", day=self.past(back, 2))
        self.assertNotIn("recurring:rent", self.candidates())

    def test_confidence_grows_with_history(self):
        self.healthy_month(1)
        self.assertEqual(self.candidates()["emergency_fund"]["confidence"], Recommendation.LOW)
        self.healthy_month(2); self.healthy_month(3)
        self.assertEqual(self.candidates()["emergency_fund"]["confidence"], Recommendation.HIGH)

    def test_round50_helper(self):
        self.assertEqual(rec_engine.round50(D("1")), D("50"))
        self.assertEqual(rec_engine.round50(D("168")), D("150"))
        self.assertEqual(rec_engine.round50(D("2250")), D("2250"))


class LifecycleTests(RecBase):
    def test_refresh_is_idempotent_and_sets_dates(self):
        self.healthy_month()
        self.by_key(); keys = self.by_key()
        self.assertEqual(Recommendation.objects.filter(user=self.user).count(), len(keys))
        r = keys["emergency_fund"]
        self.assertEqual((r.status, r.generated_on, r.review_date), ("PENDING", self.today, self.today + timedelta(days=14)))

    def test_pending_refreshes_with_new_numbers_but_accepted_is_untouched(self):
        self.healthy_month()
        r = self.by_key()["emergency_fund"]
        r.set_status("ACCEPTED")
        before = r.evidence
        self.healthy_month(2, saved=2000)                                         # data changes
        r2 = self.by_key()["emergency_fund"]
        self.assertEqual((r2.status, r2.evidence), ("ACCEPTED", before))

    def test_dismissed_is_not_resurfaced_during_cooldown_but_returns_after(self):
        self.healthy_month()
        r = self.by_key()["emergency_fund"]
        r.set_status("DISMISSED"); r.useful = False; r.save()
        self.assertEqual(self.by_key()["emergency_fund"].status, "DISMISSED")     # still dismissed
        Recommendation.objects.filter(pk=r.pk).update(status_changed_at=timezone.now() - timedelta(days=31))
        back = self.by_key()["emergency_fund"]
        self.assertEqual((back.status, back.useful), ("PENDING", None))

    def test_accepted_stays_active_even_when_trigger_goes_away(self):
        self.healthy_month()
        self.by_key()["emergency_fund"].set_status("ACCEPTED")
        self.goal(target=999999, start=50000, name="Big")                          # savings now cover > 3 months
        self.assertTrue(self.by_key()["emergency_fund"].is_active)

    def test_untriggered_pending_becomes_inactive(self):
        self.healthy_month()
        keys = self.by_key()
        self.assertTrue(keys["emergency_fund"].is_active)
        self.goal(target=999999, start=50000, name="Big")
        self.assertFalse(self.by_key()["emergency_fund"].is_active)

    def test_recommendations_are_per_student(self):
        self.healthy_month()
        self.by_key()
        self.assertEqual(Recommendation.objects.filter(user=self.other).count(), 0)
        self.assertEqual(self.by_key(self.other), {})


class ViewTests(RecBase):
    def setUp(self):
        super().setUp()
        self.healthy_month()
        self.rec = self.by_key()["emergency_fund"]

    def post_status(self, status, pk=None):
        return self.client.post(reverse("advisor:recommendation_status", args=[pk or self.rec.pk]), {"status": status})

    def test_page_shows_evidence_and_all_required_parts(self):
        r = self.client.get(reverse("advisor:recommendations"))
        self.assertEqual(r.status_code, 200)
        for text in ("Build your emergency fund", "Evidence", "Suggested action", "Suggested amount", "Estimated impact",
                     "confidence", "priority", "review by", "Accept", "Dismiss", "not professional financial advice"):
            self.assertContains(r, text)

    def test_status_workflow(self):
        self.post_status("ACCEPTED"); self.rec.refresh_from_db()
        self.assertEqual(self.rec.status, "ACCEPTED"); first = self.rec.accepted_at
        self.assertIsNotNone(first)
        self.post_status("COMPLETED"); self.rec.refresh_from_db()
        self.assertEqual((self.rec.status, self.rec.accepted_at), ("COMPLETED", first))
        self.post_status("PENDING"); self.rec.refresh_from_db()
        self.assertEqual((self.rec.status, self.rec.accepted_at), ("PENDING", None))
        self.post_status("DISMISSED"); self.rec.refresh_from_db()
        self.assertEqual(self.rec.status, "DISMISSED")

    def test_invalid_status_is_rejected(self):
        self.post_status("HACKED"); self.rec.refresh_from_db()
        self.assertEqual(self.rec.status, "PENDING")

    def test_status_change_requires_post_and_login(self):
        self.assertEqual(self.client.get(reverse("advisor:recommendation_status", args=[self.rec.pk])).status_code, 405)
        self.client.logout()
        self.assertEqual(self.post_status("ACCEPTED").status_code, 302)
        self.rec.refresh_from_db(); self.assertEqual(self.rec.status, "PENDING")

    def test_cannot_touch_another_students_recommendation(self):
        self.client.logout(); self.client.login(username="bob", password=self.PASSWORD)
        self.assertEqual(self.post_status("DISMISSED").status_code, 404)
        self.assertEqual(self.client.post(reverse("advisor:recommendation_feedback", args=[self.rec.pk]), {"useful": "yes"}).status_code, 404)
        self.rec.refresh_from_db(); self.assertEqual((self.rec.status, self.rec.useful), ("PENDING", None))
        self.assertNotContains(self.client.get(reverse("advisor:recommendations")), "Build your emergency fund")

    def test_feedback(self):
        url = reverse("advisor:recommendation_feedback", args=[self.rec.pk])
        self.client.post(url, {"useful": "yes"}); self.rec.refresh_from_db(); self.assertIs(self.rec.useful, True)
        self.client.post(url, {"useful": "no"}); self.rec.refresh_from_db(); self.assertIs(self.rec.useful, False)
        self.client.post(url, {"useful": "maybe"}); self.rec.refresh_from_db(); self.assertIs(self.rec.useful, False)

    def test_health_page_links_with_pending_count(self):
        r = self.client.get(reverse("advisor:tips"))
        self.assertContains(r, "Recommendations")
        self.assertGreaterEqual(r.context["pending_count"], 1)


class OutcomeTests(RecBase):
    def make(self, accepted_days_ago, with_category=True, baseline="1500", key="category_rise:Entertainment"):
        r = Recommendation.objects.create(
            user=self.user, key=key, title="t", observation="o", evidence="e", explanation="x", action="a",
            confidence="MEDIUM", priority="MEDIUM", generated_on=self.today, review_date=self.today, status="ACCEPTED",
            category=cat("Entertainment") if with_category else None, baseline_monthly=D(baseline),
            accepted_at=timezone.now() - timedelta(days=accepted_days_ago))
        return r

    def test_no_outcome_without_category_or_when_not_accepted(self):
        self.assertIsNone(rec_engine.outcome(self.make(30, with_category=False, key="k1"), self.today))
        r = self.make(30, key="k2"); r.status = "PENDING"
        self.assertIsNone(rec_engine.outcome(r, self.today))

    def test_too_early(self):
        o = rec_engine.outcome(self.make(5), self.today)
        self.assertFalse(o["ready"]); self.assertIn("Too early", o["text"])

    def test_lower_spending_reported_with_causation_caveat(self):
        r = self.make(30)
        self.expense(300, category="Entertainment")
        o = rec_engine.outcome(r, self.today)
        self.assertTrue(o["ready"])
        self.assertLess(o["per_month"], D("1500"))
        self.assertIn("lower than", o["text"])
        self.assertIn("does not prove", o["text"])

    def test_higher_spending_reported(self):
        r = self.make(30, baseline="100")
        self.expense(3000, category="Entertainment")
        self.assertIn("higher than", rec_engine.outcome(r, self.today)["text"])

    def test_outcome_only_counts_own_spending(self):
        r = self.make(30)
        self.expense(99999, category="Entertainment", user=self.other)
        self.assertEqual(rec_engine.outcome(r, self.today)["per_month"], D("0.00"))
