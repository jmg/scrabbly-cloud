"""Browser and handled errors go to Jentry; nothing is sent without a DSN."""
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from accounts.context_processors import error_reporting

DSN = "https://abcdef0123456789@jentry.example/86"


class ErrorReportingContextTests(SimpleTestCase):
    def ctx(self):
        return error_reporting(RequestFactory().get("/"))

    @override_settings(DEBUG=False, SENTRY_DSN="")
    def test_nothing_without_a_dsn(self):
        self.assertEqual(self.ctx(), {})

    @override_settings(DEBUG=True, SENTRY_DSN=DSN)
    def test_nothing_in_debug(self):
        self.assertEqual(self.ctx(), {})

    @override_settings(DEBUG=False, SENTRY_DSN=DSN, SENTRY_ENVIRONMENT="production",
                       SENTRY_RELEASE="abc123")
    def test_production_gets_the_backend_dsn(self):
        self.assertEqual(self.ctx(), {"sentry_browser_dsn": DSN,
                                      "sentry_environment": "production",
                                      "sentry_release": "abc123"})

    @override_settings(DEBUG=False, SENTRY_DSN="https://pub:secret@jentry.example/86")
    def test_a_legacy_secret_never_reaches_the_page(self):
        self.assertEqual(self.ctx()["sentry_browser_dsn"], "https://pub@jentry.example/86")


class BaseTemplateTests(TestCase):
    @override_settings(DEBUG=False, SENTRY_DSN=DSN, SENTRY_ENVIRONMENT="production",
                       SENTRY_RELEASE="abc123")
    def test_pages_load_the_browser_sdk_in_production(self):
        html = self.client.get("/").content.decode()
        self.assertIn("browser.sentry-cdn.com/7.120.0/bundle.min.js", html)
        self.assertIn('integrity="sha384-', html)
        self.assertIn(DSN, html)
        self.assertIn('environment: "production"', html)

    @override_settings(SENTRY_DSN="")
    def test_no_sdk_without_a_dsn(self):
        self.assertNotIn("sentry-cdn", self.client.get("/").content.decode())


class HandledFailuresTests(TestCase):
    def test_a_failed_live_push_is_reported_and_the_note_kept(self):
        from accounts.models import User
        from accounts.notifications import notify

        user = User.objects.create_user("ana", password="x" * 12)
        layer = mock.Mock()
        layer.group_send = mock.AsyncMock(side_effect=ConnectionError("redis down"))
        with mock.patch("accounts.notifications.get_channel_layer", return_value=layer), \
                mock.patch("accounts.notifications.sentry_sdk.capture_exception") as cap:
            note = notify(user, "hola")
        self.assertIsNotNone(note)
        cap.assert_called_once()
