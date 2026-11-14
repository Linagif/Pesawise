from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.testing import BaseTestCase

User = get_user_model()


class RegistrationLoginTests(TestCase):
    def test_register_creates_user_profile_and_logs_in(self):
        r = self.client.post(reverse("accounts:register"), {
            "full_name": "Wanjiru Kamau", "email": "w@example.com", "username": "wanjiru",
            "password1": "Tr1cky-Passw0rd!", "password2": "Tr1cky-Passw0rd!"})
        self.assertRedirects(r, reverse("dashboard:home"))
        u = User.objects.get(username="wanjiru")
        self.assertEqual((u.first_name, u.last_name), ("Wanjiru", "Kamau"))
        self.assertTrue(hasattr(u, "profile"))
        self.assertNotEqual(u.password, "Tr1cky-Passw0rd!")            # hashed
        self.assertIn("$", u.password)                                  # "<algorithm>$..." hash format
        self.assertTrue(u.check_password("Tr1cky-Passw0rd!"))
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)

    def test_register_rejects_duplicate_email_and_weak_password(self):
        User.objects.create_user("x", "dup@example.com", "Tr1cky-Passw0rd!")
        r = self.client.post(reverse("accounts:register"), {
            "full_name": "A B", "email": "DUP@example.com", "username": "newone", "password1": "123", "password2": "123"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="newone").exists())

    def test_login_and_logout(self):
        User.objects.create_user("sam", "s@example.com", "Tr1cky-Passw0rd!")
        r = self.client.post(reverse("login"), {"username": "sam", "password": "Tr1cky-Passw0rd!"})
        self.assertRedirects(r, reverse("dashboard:home"))
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 302)

    def test_bad_login_rejected(self):
        User.objects.create_user("sam", "s@example.com", "Tr1cky-Passw0rd!")
        r = self.client.post(reverse("login"), {"username": "sam", "password": "wrong"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_page_and_email(self):
        from django.core import mail
        User.objects.create_user("sam", "s@example.com", "Tr1cky-Passw0rd!")
        self.client.post(reverse("password_reset"), {"email": "s@example.com"})
        self.assertEqual(len(mail.outbox), 1)


class AccessControlTests(TestCase):
    def test_every_private_page_requires_login(self):
        names = ["dashboard:home", "dashboard:reports", "income:list", "income:add", "budgets:list", "budgets:create",
                 "expenses:list", "expenses:daily", "expenses:add", "savings:list", "savings:add", "advisor:tips",
                 "core:list", "accounts:profile"]
        for n in names:
            r = self.client.get(reverse(n))
            self.assertEqual(r.status_code, 302, n)
            self.assertIn("/accounts/login/", r["Location"], n)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)


class ProfileTests(BaseTestCase):
    def test_update_profile_and_daily_target(self):
        r = self.client.post(reverse("accounts:profile"), {"full_name": "Alice Njeri", "email": "a2@example.com",
                                                            "daily_spending_target": "450.00"})
        self.assertRedirects(r, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Njeri")
        self.assertEqual(str(self.user.profile.daily_spending_target), "450.00")

    def test_cannot_take_another_users_email(self):
        r = self.client.post(reverse("accounts:profile"), {"full_name": "Alice", "email": "bob@example.com"})
        self.assertEqual(r.status_code, 200)
