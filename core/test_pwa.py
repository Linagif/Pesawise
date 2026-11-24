import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import TestCase
from django.urls import resolve, reverse
from PIL import Image

from core import pwa


class ManifestTests(TestCase):
    def setUp(self):
        self.response = self.client.get(reverse("pwa:manifest"))
        self.data = json.loads(self.response.content)

    def test_served_publicly_with_the_right_type(self):
        self.assertEqual(self.response.status_code, 200)                      # no login needed
        self.assertEqual(self.response["Content-Type"], "application/manifest+json")

    def test_required_installability_fields(self):
        d = self.data
        self.assertEqual((d["display"], d["scope"], d["id"]), ("standalone", "/", "/"))
        self.assertTrue(d["name"] and d["short_name"] and d["theme_color"] and d["background_color"])
        self.assertTrue(d["start_url"].startswith(d["scope"]))

    def test_icons_exist_with_the_declared_sizes(self):
        sizes = {(i["sizes"], i["purpose"]) for i in self.data["icons"]}
        self.assertTrue({("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes)
        for icon in self.data["icons"]:
            name = Path(icon["src"]).name
            path = Path(settings.BASE_DIR) / "static" / "pwa" / name
            self.assertTrue(path.exists(), name)
            w, h = Image.open(path).size
            self.assertEqual(f"{w}x{h}", icon["sizes"], name)

    def test_shortcuts_point_to_real_pages(self):
        self.assertEqual(len(self.data["shortcuts"]), 3)
        for s in self.data["shortcuts"]:
            self.assertEqual(resolve(s["url"]).func.__name__ != "", True)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("pwa:manifest")).status_code, 405)


class ServiceWorkerFileTests(TestCase):
    def test_headers_allow_root_scope_and_prompt_updates(self):
        r = self.client.get(reverse("pwa:sw"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("application/javascript"))
        self.assertEqual(r["Service-Worker-Allowed"], "/")
        self.assertEqual(r["Cache-Control"], "no-cache")
        self.assertEqual(reverse("pwa:sw"), "/sw.js")                          # must be at the root to control the site

    def test_contains_version_and_offline_url(self):
        body = self.client.get(reverse("pwa:sw")).content.decode()
        self.assertIn(pwa.PWA_VERSION, body)
        self.assertIn('"/offline/"', body)

    def test_offline_page_is_public_and_self_contained(self):
        r = self.client.get(reverse("pwa:offline"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("You are offline", html)
        self.assertNotIn("cdn.jsdelivr", html)                                  # must work with no network
        self.assertNotRegex(html, r"<link[^>]+stylesheet")
        self.assertNotIn("csrfmiddlewaretoken", html)                           # no personal or session content

    def test_pages_link_the_manifest_and_script(self):
        html = self.client.get(reverse("login")).content.decode()
        for needle in ('rel="manifest"', 'name="theme-color"', "apple-touch-icon", "js/pwa.js", 'data-sw="/sw.js"'):
            self.assertIn(needle, html)

    def test_install_button_and_instructions_for_signed_in_students(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user("pwa", "p@example.com", "S3cure-pass-987")
        self.client.login(username="pwa", password="S3cure-pass-987")
        self.assertContains(self.client.get(reverse("dashboard:home")), 'id="installBtn"')
        self.assertContains(self.client.get(reverse("accounts:profile")), "Add to Home Screen")


@skipUnless(shutil.which("node"), "Node.js is needed to execute the service worker")
class ServiceWorkerBehaviourTests(TestCase):
    """Runs the real service worker in Node against mock browser APIs (see core/tests_support/sw_harness.js)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = cls().client_class().get(reverse("pwa:sw")).content
        with tempfile.NamedTemporaryFile("wb", suffix=".js", delete=False) as f:
            f.write(source)
        harness = Path(settings.BASE_DIR) / "core" / "tests_support" / "sw_harness.js"
        done = subprocess.run(["node", str(harness), f.name], capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise AssertionError(f"harness failed: {done.stderr}")
        cls.out = json.loads(done.stdout.strip().splitlines()[-1])

    def test_installs_the_offline_page_and_icons(self):
        self.assertIn("/offline/", self.out["precached"])
        self.assertTrue(any(p.endswith("icon-192.png") for p in self.out["precached"]))

    def test_never_intercepts_form_posts_or_other_sites(self):
        self.assertFalse(self.out["post"])
        self.assertFalse(self.out["crossOrigin"])

    def test_pages_come_from_the_network_and_are_never_stored(self):
        self.assertEqual(self.out["navOnline"], {"handled": True, "body": "PRIVATE-EXPENSE-PAGE"})
        self.assertNotIn("/expenses/daily/", self.out["cachedAfterNav"])
        self.assertEqual(sorted(self.out["cachedAfterNav"]), sorted(self.out["precached"]))      # cache unchanged

    def test_downloads_and_data_requests_are_not_handled_or_cached(self):
        self.assertFalse(self.out["download"])
        self.assertNotIn("/reports/export/pdf/", self.out["cachedAfterDownload"])

    def test_static_files_are_cached_and_work_offline(self):
        self.assertTrue(self.out["staticFirst"]["handled"])
        self.assertIn("/static/css/style.css", self.out["cachedAfterStatic"])
        self.assertTrue(self.out["staticOffline"]["handled"])
        self.assertIn("style.css", self.out["staticOffline"]["body"])                            # served from cache

    def test_offline_navigation_shows_the_offline_page_not_stale_data(self):
        self.assertEqual(self.out["navOffline"]["body"], "precached:/offline/")

    def test_old_versions_are_cleaned_but_other_caches_untouched(self):
        names = self.out["cachesAfterActivate"]
        self.assertNotIn("pesawise-static-old", names)
        self.assertIn("someone-elses-cache", names)
        self.assertIn(self.out["cacheName"], names)
