import re
import tempfile
from pathlib import Path

from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse


def render(path):
    return Template("{% load assets %}{% asset '" + path + "' %}").render(Context()).strip()


class AssetTagTests(TestCase):
    def test_url_carries_a_content_hash(self):
        self.assertRegex(render("js/theme.js"), r"^/static/js/theme\.js\?v=[0-9a-f]{8}$")

    def test_hash_changes_when_the_file_changes_so_old_copies_are_never_reused(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(STATICFILES_DIRS=[folder]):
            f = Path(folder) / "x.js"
            f.write_text("version one")
            first = render("x.js")
            self.assertEqual(render("x.js"), first)                    # stable while unchanged
            f.write_text("version two, longer")
            self.assertNotEqual(render("x.js"), first)

    def test_missing_file_falls_back_to_the_plain_url(self):
        self.assertEqual(render("js/does-not-exist.js"), "/static/js/does-not-exist.js")

    def test_every_page_uses_versioned_urls_for_its_own_css_and_js(self):
        html = self.client.get(reverse("login")).content.decode()
        for name in ("css/style.css", "js/app.js", "js/theme.js", "js/pwa.js"):
            self.assertRegex(html, rf"/static/{re.escape(name)}\?v=[0-9a-f]{{8}}", name)
