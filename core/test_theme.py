import json
import re
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
CSS = (BASE / "static" / "css" / "style.css").read_text()


def _vars(block):
    return dict(re.findall(r"--(pw-[\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _blocks():
    light = _vars(re.search(r":root\{(.*?)\n\}", CSS, re.S).group(1))
    dark = {**light, **_vars(re.search(r'\[data-bs-theme="dark"\]\{(.*?)\n\}', CSS, re.S).group(1))}
    return light, dark


def _lum(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class ContrastTests(TestCase):
    """WCAG AA: normal text needs a contrast ratio of at least 4.5."""

    PAIRS = [("pw-text", "pw-bg"), ("pw-text", "pw-surface"), ("pw-muted", "pw-bg"), ("pw-muted", "pw-surface"),
             ("pw-link", "pw-bg"), ("pw-link", "pw-surface"), ("pw-in", "pw-surface"), ("pw-out", "pw-surface"),
             ("pw-save", "pw-surface")]

    def check(self, theme, palette):
        for fg, bg in self.PAIRS:
            ratio = contrast(palette[fg], palette[bg])
            self.assertGreaterEqual(ratio, 4.5, f"{theme}: {fg} {palette[fg]} on {bg} {palette[bg]} is only {ratio:.2f}")

    def test_light_palette(self):
        self.check("light", _blocks()[0])

    def test_dark_palette(self):
        self.check("dark", _blocks()[1])

    def test_fixed_colour_pairs_in_both_themes(self):
        light, dark = _blocks()
        for palette in (light, dark):
            self.assertGreaterEqual(contrast("#ffffff", palette["pw-green"]), 4.5)       # white text on green buttons
        self.assertGreaterEqual(contrast("#2b2100", "#f2b705"), 4.5)                     # text on the gold button
        self.assertGreaterEqual(contrast("#cfe0d8", "#0b2e24"), 4.5)                     # sidebar links
        self.assertGreaterEqual(contrast("#9db0a6", "#17211d"), 4.5)                     # chart text on dark cards

    def test_every_theme_variable_is_defined_for_dark(self):
        light, dark = _blocks()
        for name in ("pw-bg", "pw-surface", "pw-text", "pw-muted", "pw-line", "pw-link", "pw-in", "pw-out", "pw-save"):
            self.assertNotEqual(light[name], dark[name], name)                          # dark really changes the colour


class TemplateWiringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("dm", "d@example.com", "S3cure-pass-987")

    def assert_three_choices(self, html, expected):
        for choice in ("light", "dark", "system"):
            self.assertEqual(html.count(f'data-theme-choice="{choice}"'), expected, choice)

    def test_login_page_offers_light_dark_and_device_choices(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assert_three_choices(html, 1)
        for label in ("Light", "Dark", "Device default"):
            self.assertIn(label, html)
        self.assertIn("data-theme-current", html)
        self.assertRegex(html, r'<script[^>]+src="/static/js/theme\.js\?v=[0-9a-f]{8}"')   # a REAL script tag, not just a mention

    def test_theme_js_is_loaded_on_signed_in_pages_too(self):
        self.client.login(username="dm", password="S3cure-pass-987")
        for name in ("dashboard:home", "accounts:profile", "expenses:daily"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertRegex(html, r'<script[^>]+src="/static/js/theme\.js', name)

    def test_early_script_runs_before_any_stylesheet(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertLess(html.index("pw-theme"), html.index("bootstrap.min.css"))        # applied before any CSS loads: no flash

    def test_signed_in_pages_have_the_menu_once_in_the_top_bar(self):
        self.client.login(username="dm", password="S3cure-pass-987")
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assert_three_choices(html, 1)
        self.assertLess(html.index("topbar"), html.index('data-theme-choice="light"'))

    def test_profile_page_has_an_appearance_section(self):
        self.client.login(username="dm", password="S3cure-pass-987")
        html = self.client.get(reverse("accounts:profile")).content.decode()
        self.assertIn("Appearance", html)
        self.assert_three_choices(html, 2)                                              # top-bar menu + Appearance card

    def test_choices_are_buttons_not_links_so_nothing_navigates(self):
        html = self.client.get(reverse("login")).content.decode()
        for m in re.finditer(r'<(\w+)[^>]*data-theme-choice="\w+"', html):
            self.assertEqual(m.group(1), "button")

    def test_dashboard_charts_redraw_on_theme_change(self):
        self.client.login(username="dm", password="S3cure-pass-987")
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn('addEventListener("themechange"', html)
        self.assertIn("function colors()", html)

    def test_offline_page_supports_dark(self):
        self.assertIn("prefers-color-scheme: dark", self.client.get(reverse("pwa:offline")).content.decode())

    def test_theme_is_not_stored_on_the_server(self):
        self.client.login(username="dm", password="S3cure-pass-987")
        response = self.client.get(reverse("dashboard:home"))
        self.assertNotIn("pw-theme", "".join(c.value for c in response.cookies.values()))


@skipUnless(shutil.which("node"), "Node.js is needed to execute the theme scripts")
class ThemeScriptBehaviourTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        page = cls().client_class().get(reverse("login")).content.decode()
        early = re.search(r"<script>/\* apply the saved theme.*?</script>", page, re.S).group(0)
        early_js = re.sub(r"^<script>|</script>$", "", early)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(early_js)
        harness = BASE / "core" / "tests_support" / "theme_harness.js"
        done = subprocess.run(["node", str(harness), str(BASE / "static" / "js" / "theme.js"), f.name],
                              capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise AssertionError(done.stderr)
        cls.out = json.loads(done.stdout.strip().splitlines()[-1])

    def test_resolution_rules(self):
        r = self.out["resolve"]
        self.assertEqual((r["dark|false"], r["light|true"], r["system|true"], r["system|false"]), ("dark", "light", "dark", "light"))
        self.assertEqual((r["weird|true"], r["weird|false"], r["null|true"]), ("dark", "light", "dark"))   # unknown = device default
        self.assertEqual(self.out["choices"], ["light", "dark", "system"])

    def test_first_visit_follows_the_device(self):
        i = self.out["initial"]
        self.assertEqual((i["attr"], i["label"], i["icon"], i["active"]), ("dark", "Device default", "bi bi-circle-half", ["system"]))
        self.assertEqual(i["events"], ["themechange:dark"])

    def test_picking_light_then_dark_then_device(self):
        light, dark, system = self.out["pickLight"], self.out["pickDark"], self.out["pickSystem"]
        self.assertEqual((light["attr"], light["stored"], light["label"], light["icon"]), ("light", "light", "Light", "bi bi-sun"))
        self.assertEqual((dark["attr"], dark["stored"], dark["label"], dark["icon"]), ("dark", "dark", "Dark", "bi bi-moon-stars"))
        self.assertEqual((system["attr"], system["stored"], system["label"]), ("dark", "system", "Device default"))   # device is dark

    def test_exactly_one_choice_is_highlighted_and_announced(self):
        for key, name in (("pickLight", "light"), ("pickDark", "dark"), ("pickSystem", "system")):
            self.assertEqual(self.out[key]["active"], [name], key)
            self.assertEqual(self.out[key]["checked"], [name], key)                    # aria-checked for screen readers

    def test_appearance_card_buttons_work_and_use_aria_pressed(self):
        p = self.out["profileButton"]
        self.assertEqual((p["attr"], p["stored"]), ("dark", "dark"))
        self.assertEqual(p["profileDark"], {"active": True, "pressed": "true"})

    def test_button_has_an_accessible_name(self):
        self.assertIn("Theme:", self.out["pickDark"]["aria"])

    def test_tells_the_charts_when_the_theme_changes(self):
        self.assertEqual(self.out["eventsAfterPicks"], ["themechange:light", "themechange:dark"])   # one event per pick, in order

    def test_malformed_clicks_and_values_are_ignored(self):
        self.assertTrue(self.out["ignoresBadClicks"])

    def test_saved_choice_is_restored(self):
        s = self.out["savedDarkRestored"]
        self.assertEqual((s["attr"], s["active"]), ("dark", ["dark"]))

    def test_device_default_follows_the_device_but_explicit_choices_do_not(self):
        self.assertEqual(self.out["systemFollowsDevice"], "dark")
        self.assertEqual(self.out["lightIgnoresDevice"], "light")

    def test_blocked_storage_never_breaks_the_page_and_choice_still_works(self):
        self.assertEqual(self.out["brokenStorage"], {"read": "system", "writeThrows": False})
        b = self.out["blockedStorageClick"]
        self.assertEqual((b["attr"], b["stored"]), ("dark", None))                    # works for this visit, nothing saved
        self.assertFalse(self.out["earlyBrokenStorageThrows"])
        self.assertEqual(self.out["invalidStored"], "system")

    def test_inline_script_agrees_with_the_main_script_in_every_case(self):
        for case, v in self.out["early"].items():
            self.assertEqual(v["early"], v["full"], case)
