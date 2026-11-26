import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

BASE = Path(settings.BASE_DIR)


def _jsdom_available():
    if not shutil.which("node"):
        return False
    probe = subprocess.run(["node", "-e", "require('jsdom')"], cwd=BASE, capture_output=True, env=os.environ.copy())
    return probe.returncode == 0


@skipUnless(_jsdom_available(), "needs Node.js and jsdom (npm install --no-save jsdom)")
class ThemeEndToEndTests(TestCase):
    """Real pages + the page's own <script> tags + real clicks. This is what catches a script that was never included."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = get_user_model().objects.create_user("e2e", "e@example.com", "S3cure-pass-987")
        client = cls().client_class()
        pages = {"login": client.get(reverse("login")).content.decode()}
        client.login(username="e2e", password="S3cure-pass-987")
        pages["dashboard"] = client.get(reverse("dashboard:home")).content.decode()
        pages["profile"] = client.get(reverse("accounts:profile")).content.decode()
        user.delete()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(pages, f)
        done = subprocess.run(["node", str(BASE / "core" / "tests_support" / "theme_e2e.js"), f.name, str(BASE / "static")],
                              capture_output=True, text=True, timeout=120, cwd=BASE)
        if done.returncode != 0:
            raise AssertionError(done.stderr)
        cls.out = json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_page_really_loads_theme_js(self):
        for name, r in self.out.items():
            self.assertIn("theme.js", r["loaded"], f"{name}: theme.js is never loaded by the page")

    def test_clicking_the_menu_changes_the_theme_on_every_page(self):
        for name, r in self.out.items():
            self.assertEqual((r["afterDark"], r["stored"], r["label"]), ("dark", "dark", "Dark"), name)
            self.assertIn("dark", r["active"], name)
            self.assertEqual((r["afterLight"], r["afterIconClick"], r["afterSystem"]), ("light", "dark", "light"), name)

    def test_no_script_errors_apart_from_the_charts_that_need_the_cdn(self):
        for name, r in self.out.items():
            self.assertEqual(r["errorsOtherThanCharts"], [], name)

    def test_appearance_card_and_menu_both_respond(self):
        self.assertEqual(self.out["profile"]["choices"], 6)
        self.assertEqual(self.out["profile"]["active"], ["dark", "dark"])
