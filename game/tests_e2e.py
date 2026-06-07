"""End-to-end browser tests (Playwright) for the JS-heavy flows.

These drive a real Chromium against Django's live server, covering things unit
tests can't: the interactive puzzle board and the lobby/auth UI.

They require a browser. Install it once in an environment with network access:

    pip install -r requirements-dev.txt
    python -m playwright install chromium

The whole suite skips cleanly if Playwright or a browser isn't available, so
`manage.py test` stays green without them. Run just these with:

    python manage.py test game.tests_e2e
"""

import unittest

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_PLAYWRIGHT = False

_LAUNCH_ARGS = ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]


def _launch(pw):
    """Launch Chromium: the Playwright-managed build, else a system browser."""
    try:
        return pw.chromium.launch(args=_LAUNCH_ARGS)
    except Exception:
        for path in ("/usr/bin/chromium", "/usr/bin/chromium-browser",
                     "/usr/bin/google-chrome"):
            try:
                return pw.chromium.launch(executable_path=path, args=_LAUNCH_ARGS)
            except Exception:
                continue
    return None


@unittest.skipUnless(_HAS_PLAYWRIGHT, "playwright not installed")
class BrowserE2ETests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._pw = sync_playwright().start()
        cls._browser = _launch(cls._pw)
        if cls._browser is None:
            cls._pw.stop()
            raise unittest.SkipTest("no Chromium available to drive")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_browser", None):
            cls._browser.close()
            cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        self.page = self._browser.new_page()

    def tearDown(self):
        self.page.close()

    # -- tests ---------------------------------------------------------------
    def test_landing_loads_for_guest(self):
        self.page.goto(self.live_server_url + "/")
        # Guests see the marketing landing with a prominent play CTA.
        self.assertTrue(self.page.locator("text=Scrabbly").first.is_visible())
        self.assertTrue(self.page.locator(".hero h1").is_visible())

    def test_register_flow(self):
        self.page.goto(self.live_server_url + "/register/")
        self.page.fill("input[name=username]", "e2euser")
        self.page.fill("input[name=password]", "abcd1234")
        self.page.click("button[type=submit]")
        self.page.wait_for_url("**/")
        self.assertIn("e2euser", self.page.content())

    def test_puzzle_place_and_reveal(self):
        from game import puzzles
        from game.services import get_wordlist
        if not get_wordlist("es").enabled:
            self.skipTest("dictionary not bundled")
        puzzle = puzzles.new_training_puzzle("es")
        self.assertIsNotNone(puzzle)

        self.page.goto(f"{self.live_server_url}/puzzles/{puzzle.id}/")
        self.page.wait_for_selector("#board .cell")
        # Place the first rack tile on the first empty cell.
        self.page.locator("#rack .rack-tile").first.click()
        self.page.locator("#board .cell:not(.filled)").first.click()
        self.assertEqual(self.page.locator("#board .cell.pending").count(), 1)

        # Reveal the solution and confirm the result panel shows it.
        self.page.click("#btn-reveal")
        self.page.wait_for_selector("#puzzle-result .puzzle-miss")
        self.assertIn("+", self.page.inner_text("#puzzle-result"))
