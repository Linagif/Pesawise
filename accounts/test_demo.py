import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from advisor import analysis as an
from advisor import simulator as sim
from advisor.recommendations import refresh_recommendations
from budgets.models import Budget
from core import demo
from expenses.models import Expense
from imports.models import ImportedTransaction
from savings.models import SavingsGoal

User = get_user_model()
ENABLED = {"DJANGO_DEMO_ENABLED": "1"}


class DemoSwitchTests(TestCase):
    def test_off_by_default_in_production_like_settings(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DJANGO_DEMO_ENABLED", None)
            self.assertFalse(demo.demo_enabled())
            self.assertEqual(self.client.post(reverse("accounts:demo")).status_code, 404)
            self.assertEqual(User.objects.count(), 0)
            self.assertNotContains(self.client.get(reverse("login")), "Try the demo")

    def test_button_shown_when_enabled(self):
        with mock.patch.dict(os.environ, ENABLED):
            self.assertContains(self.client.get(reverse("login")), "Try the demo")


@mock.patch.dict(os.environ, ENABLED)
class VisitorDemoTests(TestCase):
    def start(self):
        return self.client.post(reverse("accounts:demo"))

    def test_creates_private_logged_in_sandbox_with_data(self):
        r = self.start()
        self.assertRedirects(r, reverse("dashboard:home"))
        u = User.objects.get(profile__is_demo=True)
        self.assertTrue(u.username.startswith("demo-"))
        self.assertFalse(u.has_usable_password())
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)
        self.assertEqual(self.client.session.get_expiry_age(), demo.SESSION_SECONDS)
        self.assertGreater(Expense.objects.filter(user=u).count(), 50)
        self.assertEqual((Budget.objects.filter(user=u).count(), SavingsGoal.objects.filter(user=u).count()), (2, 2))

    def test_requires_post_and_csrf_safe_method_only(self):
        self.assertEqual(self.client.get(reverse("accounts:demo")).status_code, 405)

    def test_cannot_log_in_to_a_demo_account_with_any_password(self):
        self.start()
        u = User.objects.get(profile__is_demo=True)
        for pw in ("", "demo", "password", u.username):
            self.assertIsNone(authenticate(username=u.username, password=pw))

    def test_each_visitor_gets_separate_data(self):
        self.start()
        first = User.objects.get(profile__is_demo=True)
        other_client = self.client_class()
        other_client.post(reverse("accounts:demo"))
        self.assertEqual(User.objects.filter(profile__is_demo=True).count(), 2)
        second = User.objects.exclude(pk=first.pk).get(profile__is_demo=True)
        Expense.objects.filter(user=second).delete()
        self.assertGreater(Expense.objects.filter(user=first).count(), 0)             # untouched
        mine = Expense.objects.filter(user=first).first()
        self.assertEqual(other_client.get(reverse("expenses:edit", args=[mine.pk])).status_code, 404)

    def test_banner_shown_only_for_demo_accounts(self):
        self.start()
        self.assertContains(self.client.get(reverse("dashboard:home")), "Demo account")
        real = User.objects.create_user("real", "r@example.com", "S3cure-pass-987")
        self.client.logout(); self.client.login(username="real", password="S3cure-pass-987")
        self.assertNotContains(self.client.get(reverse("dashboard:home")), "Demo account")

    def test_expired_demos_are_purged_but_real_accounts_never(self):
        self.start()
        old = User.objects.get(profile__is_demo=True)
        User.objects.filter(pk=old.pk).update(date_joined=timezone.now() - timedelta(hours=demo.DEMO_LIFETIME_HOURS + 1))
        real = User.objects.create_user("veteran", "v@example.com", "S3cure-pass-987")
        User.objects.filter(pk=real.pk).update(date_joined=timezone.now() - timedelta(days=900))
        fresh = self.client_class(); fresh.post(reverse("accounts:demo"))               # also triggers a purge
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertEqual(Expense.objects.filter(user_id=old.pk).count(), 0)            # its data went with it
        self.assertTrue(User.objects.filter(pk=real.pk).exists())
        self.assertEqual(User.objects.filter(profile__is_demo=True).count(), 1)

    def test_capacity_cap(self):
        with mock.patch.object(demo, "MAX_ACTIVE_DEMOS", 1):
            self.start()
            second = self.client_class()
            r = second.post(reverse("accounts:demo"), follow=True)
            self.assertRedirects(r, reverse("login"))
            self.assertContains(r, "demo is busy")
            self.assertEqual(User.objects.filter(profile__is_demo=True).count(), 1)

    def test_purge_command(self):
        from django.core.management import call_command
        self.start()
        User.objects.update(date_joined=timezone.now() - timedelta(days=2))
        call_command("purge_demo")
        self.assertEqual(User.objects.count(), 0)


class DemoDataQualityTests(TestCase):
    """The demo must make every feature look good on the very first click."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, ENABLED)      # a class decorator would not cover setUp
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.post(reverse("accounts:demo"))
        self.user = User.objects.get(profile__is_demo=True)
        self.today = timezone.localdate()

    def test_every_page_renders(self):
        for name in ("dashboard:home", "dashboard:reports", "income:list", "budgets:list", "expenses:daily", "expenses:list",
                     "savings:list", "advisor:tips", "advisor:simulator", "advisor:recommendations", "imports:review",
                     "imports:paste", "core:list", "accounts:profile"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_health_indicators_all_available(self):
        rep = an.build_health_report(self.user, self.today)
        self.assertTrue(all(i["available"] for i in rep["indicators"]))
        self.assertGreaterEqual(len(rep["insights"]), 3)

    def test_simulator_has_a_baseline(self):
        self.assertEqual(sim.baseline(self.user, self.today)["months_used"], 3)

    def test_recommendations_are_sensible(self):
        keys = {r.key for r in refresh_recommendations(self.user, self.today).filter(is_active=True)}
        self.assertTrue({"emergency_fund", "category_rise:Entertainment", "small_purchases"} <= keys)
        self.assertNotIn("recurring:rent", keys)                                      # never advise stopping rent

    def test_review_queue_has_three_waiting_messages_and_no_dates_in_future(self):
        rows = ImportedTransaction.objects.filter(user=self.user, status="PENDING")
        self.assertEqual(rows.count(), 3)
        self.assertTrue(all(r.occurred_on <= self.today for r in rows))
        self.assertFalse(Expense.objects.filter(user=self.user, expense_date__gt=self.today).exists())
