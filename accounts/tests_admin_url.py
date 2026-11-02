"""The admin is mounted at settings.ADMIN_URL, not at /admin/."""
import importlib

from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

import config.urls


def reload_urls():
    clear_url_caches()
    importlib.reload(config.urls)


class AdminUrlTests(TestCase):
    def tearDown(self):
        # Back to the URLconf of the real settings for the other tests.
        reload_urls()

    @override_settings(ADMIN_URL="k3x9q/")
    def test_admin_moves_to_admin_url(self):
        reload_urls()
        self.assertEqual(reverse("admin:index"), "/k3x9q/")
        r = self.client.get("/k3x9q/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/k3x9q/login/"))
        self.assertEqual(self.client.get("/k3x9q/login/").status_code, 200)

    @override_settings(ADMIN_URL="k3x9q/")
    def test_old_admin_path_is_gone(self):
        reload_urls()
        self.assertEqual(self.client.get("/admin/").status_code, 404)
        self.assertEqual(self.client.get("/admin/login/").status_code, 404)

    def test_default_is_admin(self):
        from django.conf import settings
        self.assertEqual(settings.ADMIN_URL, "admin/")
