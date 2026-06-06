from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from game import services
from game.engine import InvalidMove

User = get_user_model()


class PremiumFlowTests(TestCase):
    def _register(self, username):
        c = Client()
        c.get("/")  # provision guest + csrf
        c.post("/register/", {"username": username, "password": "abcd"})
        return c, User.objects.get(username=username)

    def test_mock_subscribe_grants_premium(self):
        c, u = self._register("prem")
        self.assertFalse(u.is_premium)
        r = c.post("/premium/subscribe/", {"plan": "monthly"})
        self.assertEqual(r.status_code, 302)  # redirect to success
        u.refresh_from_db()
        self.assertTrue(u.is_premium)
        self.assertTrue(u.subscriptions.filter(status="active").exists())

    def test_cancel_keeps_premium_until_period_end(self):
        c, u = self._register("prem2")
        c.post("/premium/subscribe/", {"plan": "monthly"})
        c.post("/premium/cancel/")
        u.refresh_from_db()
        self.assertTrue(u.is_premium)  # still entitled until period end
        self.assertTrue(u.subscriptions.filter(status="canceled").exists())

    def test_guest_cannot_subscribe(self):
        c = Client()
        c.get("/")  # becomes a guest
        r = c.post("/premium/subscribe/", {"plan": "monthly"})
        self.assertEqual(r.status_code, 302)  # bounced to register
        self.assertFalse(User.objects.filter(subscriptions__isnull=False).exists())


class PremiumGatingTests(TestCase):
    def _finished_game(self, owner):
        u2 = User.objects.create(username="opp_" + owner.username)
        g = services.join_game(services.create_game(owner, rated=False), u2)
        services.resign(g, owner)
        return g

    def test_analysis_locked_for_free_then_unlocked_for_premium(self):
        c = Client()
        c.get("/")
        c.post("/register/", {"username": "an", "password": "abcd"})
        u = User.objects.get(username="an")
        g = self._finished_game(u)

        r = c.get(f"/game/{g.pk}/analysis/")
        self.assertContains(r, "Premium", status_code=200)
        self.assertTemplateUsed(r, "game/analysis_locked.html")

        u.premium_until = timezone.now() + timedelta(days=10)
        u.save(update_fields=["premium_until"])
        r = c.get(f"/game/{g.pk}/analysis/")
        self.assertTemplateUsed(r, "game/analysis.html")

    def test_free_concurrent_game_limit(self):
        u = User.objects.create_user("lim", password="x")
        for _ in range(3):
            services.create_game(u)
        with self.assertRaises(InvalidMove):
            services.create_game(u)
        # Premium bypasses the cap.
        u.premium_until = timezone.now() + timedelta(days=1)
        u.save(update_fields=["premium_until"])
        services.create_game(u)  # should not raise

    def test_premium_theme_requires_subscription(self):
        c = Client()
        c.get("/")
        c.post("/register/", {"username": "th", "password": "abcd"})
        u = User.objects.get(username="th")

        c.post("/settings/theme/", {"theme": "wood"})  # premium-only
        u.refresh_from_db()
        self.assertEqual(u.board_theme, "classic")

        u.premium_until = timezone.now() + timedelta(days=1)
        u.save(update_fields=["premium_until"])
        c.post("/settings/theme/", {"theme": "wood"})
        u.refresh_from_db()
        self.assertEqual(u.board_theme, "wood")
        self.assertEqual(u.effective_theme, "wood")

    def test_effective_theme_falls_back_when_not_premium(self):
        u = User.objects.create_user("ft", password="x")
        u.board_theme = "midnight"
        u.save()
        self.assertEqual(u.effective_theme, "classic")  # premium theme, no sub
