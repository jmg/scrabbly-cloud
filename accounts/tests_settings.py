"""With DEBUG off the settings fail closed. Each case imports them in a fresh process."""
import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

PROBE = (
    "import json; from config import settings as s; "
    "print(json.dumps({'hosts': s.ALLOWED_HOSTS, 'dev_key': s.SECRET_KEY.startswith('dev-insecure'), "
    "'mock': s.MOCK_BILLING}))"
)


def load(**env):
    keep = {k: v for k, v in os.environ.items()
            if k not in ("DEBUG", "SECRET_KEY", "ALLOWED_HOSTS", "DJANGO_SETTINGS_MODULE")}
    return subprocess.run([sys.executable, "-c", PROBE], cwd=settings.BASE_DIR,
                          env={**keep, **env}, capture_output=True, text=True)


class FailClosedSettingsTests(SimpleTestCase):
    def test_no_key_stops_the_app_when_debug_is_off(self):
        for env in ({}, {"SECRET_KEY": ""}, {"SECRET_KEY": "change-me-in-production"},
                    {"SECRET_KEY": "dev-insecure-key-change-me-in-production"}):
            r = load(DEBUG="0", **env)
            self.assertNotEqual(r.returncode, 0, env)
            self.assertIn("ImproperlyConfigured", r.stderr)
            self.assertNotIn("change-me", r.stderr.split("ImproperlyConfigured")[-1])

    def test_no_host_is_allowed_by_default_when_debug_is_off(self):
        r = load(DEBUG="0", SECRET_KEY="a-real-one")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["hosts"], [])

    def test_production_values_are_honored(self):
        r = load(DEBUG="0", SECRET_KEY="a-real-one", ALLOWED_HOSTS="a.example,b.example")
        self.assertEqual(json.loads(r.stdout),
                         {"hosts": ["a.example", "b.example"], "dev_key": False, "mock": False})

    def test_development_still_works_with_nothing_set(self):
        r = load()
        self.assertEqual(json.loads(r.stdout), {"hosts": ["*"], "dev_key": True, "mock": True})

    def test_the_docker_build_can_run_without_hosts(self):
        # The Dockerfile runs collectstatic with DEBUG=0 and SECRET_KEY=build-only.
        r = load(DEBUG="0", SECRET_KEY="build-only")
        self.assertEqual(r.returncode, 0, r.stderr)
