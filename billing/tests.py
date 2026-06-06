from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from billing.models import Coupon, Subscription
from game import services
from game.engine import InvalidMove

User = get_user_model()


class PremiumFlowTests(TestCase):
    def _register(self, username):
        c = Client()
        c.get("/")
        c.post("/register/", {"username": username, "password": "abcd"})
        return c, User.objects.get(username=username)

    def test_subscribe_sets_tier_and_premium(self):
        c, u = self._register("prem")
        r = c.post("/premium/subscribe/", {"plan": "diamond_yearly"})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.is_premium)
        self.assertEqual(u.tier, "diamond")
        sub = u.subscriptions.get()
        self.assertEqual(sub.tier, "diamond")
        self.assertFalse(sub.is_trial)

    def test_free_trial_once(self):
        c, u = self._register("trialer")
        self.assertFalse(u.has_used_trial)
        c.post("/premium/subscribe/", {"plan": "gold_monthly", "trial": "1"})
        u.refresh_from_db()
        self.assertTrue(u.is_premium)
        self.assertTrue(u.has_used_trial)
        self.assertTrue(u.subscriptions.filter(is_trial=True).exists())
        # Trial only entitles ~7 days.
        self.assertLess(u.premium_until, timezone.now() + timedelta(days=8))

    def test_coupon_adds_bonus_days_and_is_redeemed(self):
        Coupon.objects.create(code="BONUS30", free_days=30, max_redemptions=1)
        c, u = self._register("couponer")
        c.post("/premium/subscribe/", {"plan": "gold_monthly", "coupon": "bonus30"})
        u.refresh_from_db()
        # 31 plan days + 30 bonus.
        self.assertGreater(u.premium_until, timezone.now() + timedelta(days=55))
        self.assertEqual(Coupon.objects.get(code="BONUS30").times_redeemed, 1)

    def test_invalid_coupon_is_rejected(self):
        c, u = self._register("badcoupon")
        r = c.post("/premium/subscribe/", {"plan": "gold_monthly", "coupon": "NOPE"})
        self.assertEqual(r.status_code, 302)  # bounced back to pricing
        u.refresh_from_db()
        self.assertFalse(u.is_premium)

    def test_cancel_keeps_premium_until_period_end(self):
        c, u = self._register("canceler")
        c.post("/premium/subscribe/", {"plan": "gold_monthly"})
        c.post("/premium/cancel/")
        u.refresh_from_db()
        self.assertTrue(u.is_premium)
        self.assertTrue(u.subscriptions.filter(status=Subscription.CANCELED).exists())

    def test_portal_redirects(self):
        c, u = self._register("portaler")
        c.post("/premium/subscribe/", {"plan": "gold_monthly"})
        r = c.post("/premium/portal/")
        self.assertEqual(r.status_code, 302)  # mock -> manage page


class MonetizationExtrasTests(TestCase):
    def _register(self, username, email=""):
        c = Client()
        c.get("/")
        c.post("/register/", {"username": username, "password": "abcd", "email": email})
        return c, User.objects.get(username=username)

    def test_lifetime_plan_grants_long_premium(self):
        c, u = self._register("lifer")
        c.post("/premium/subscribe/", {"plan": "diamond_lifetime"})
        u.refresh_from_db()
        self.assertTrue(u.is_premium)
        self.assertEqual(u.tier, "diamond")
        self.assertGreater(u.premium_until, timezone.now() + timedelta(days=3650))

    def test_gift_buy_and_redeem(self):
        from billing.models import GiftCode
        c1, buyer = self._register("buyer")
        r = c1.post("/premium/gift/buy/", {"plan": "gift_diamond_year"})
        self.assertEqual(r.status_code, 200)  # shows the code
        g = GiftCode.objects.get(purchaser=buyer)
        self.assertFalse(g.is_redeemed)

        c2, recipient = self._register("recipient")
        c2.post("/premium/gift/redeem/", {"code": g.code})
        recipient.refresh_from_db()
        self.assertTrue(recipient.is_premium)
        self.assertEqual(recipient.tier, "diamond")
        g.refresh_from_db()
        self.assertEqual(g.redeemed_by_id, recipient.pk)
        # A used code can't be redeemed again.
        self.assertIsNone(__import__("billing.service", fromlist=["x"]).redeem_gift(recipient, g.code))

    def test_metrics_staff_only(self):
        c, u = self._register("viewer")
        self.assertEqual(c.get("/premium/metrics/").status_code, 403)
        u.is_staff = True
        u.save(update_fields=["is_staff"])
        self.assertEqual(c.get("/premium/metrics/").status_code, 200)

    def test_welcome_email_sent_when_email_given(self):
        from django.core import mail
        mail.outbox = []
        self._register("emailer", email="e@example.com")
        self.assertTrue(any("Bienvenido" in m.subject for m in mail.outbox))

    def test_dunning_marks_past_due_and_emails(self):
        from django.core import mail
        from billing import service, views
        from billing.models import Subscription
        u = User.objects.create_user("dun", password="x", email="d@example.com")
        service.activate(u, "gold_monthly", "stripe", subscription_id="sub_123")
        mail.outbox = []
        views._handle_event({
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": "sub_123",
                                "metadata": {"user_id": str(u.pk)}}},
        })
        self.assertTrue(Subscription.objects.filter(
            provider_subscription_id="sub_123", status=Subscription.PAST_DUE).exists())
        self.assertTrue(any("pago" in m.subject.lower() for m in mail.outbox))


class PerkGatingTests(TestCase):
    def _premium(self, username, tier):
        u = User.objects.create_user(username, password="x")
        u.premium_until = timezone.now() + timedelta(days=10)
        u.premium_tier = tier
        u.save()
        return u

    def test_analysis_is_diamond_only(self):
        gold = self._premium("g", "gold")
        diamond = self._premium("d", "diamond")
        self.assertFalse(gold.has_perk("analysis"))
        self.assertTrue(diamond.has_perk("analysis"))
        # Both tiers get themes/stats/unlimited.
        for u in (gold, diamond):
            self.assertTrue(u.has_perk("themes"))
            self.assertTrue(u.has_perk("stats"))

    def test_analysis_view_gated_by_tier(self):
        owner = self._premium("an_gold", "gold")
        u2 = User.objects.create(username="an_opp")
        g = services.join_game(services.create_game(owner, rated=False), u2)
        services.resign(g, owner)
        c = Client()
        c.force_login(owner)
        # Gold cannot see analysis.
        r = c.get(f"/game/{g.pk}/analysis/")
        self.assertTemplateUsed(r, "game/analysis_locked.html")
        owner.premium_tier = "diamond"
        owner.save(update_fields=["premium_tier"])
        r = c.get(f"/game/{g.pk}/analysis/")
        self.assertTemplateUsed(r, "game/analysis.html")

    def test_free_concurrent_game_limit(self):
        u = User.objects.create_user("lim", password="x")
        for _ in range(3):
            services.create_game(u)
        with self.assertRaises(InvalidMove):
            services.create_game(u)
        u.premium_until = timezone.now() + timedelta(days=1)
        u.premium_tier = "gold"
        u.save()
        services.create_game(u)  # premium bypasses the cap

    def test_theme_perk_required(self):
        u = User.objects.create_user("th", password="x")
        u.board_theme = "midnight"
        u.save()
        self.assertEqual(u.effective_theme, "classic")  # not premium
        u.premium_until = timezone.now() + timedelta(days=1)
        u.premium_tier = "gold"
        u.save()
        self.assertEqual(u.effective_theme, "midnight")
