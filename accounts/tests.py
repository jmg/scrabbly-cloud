from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts import social
from accounts.models import Friendship
from game.models import Challenge, Game

User = get_user_model()


def _login(username):
    u = User.objects.create_user(username, password="x")
    c = Client()
    c.force_login(u)
    return c, u


class FriendshipTests(TestCase):
    def test_request_and_accept(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/friends/request/", {"username": "bob"})
        self.assertTrue(Friendship.objects.filter(
            from_user=a, to_user=b, status=Friendship.PENDING).exists())
        self.assertEqual(social.relationship(a, b), "sent")
        self.assertEqual(social.relationship(b, a), "incoming")

        fr = Friendship.objects.get(from_user=a, to_user=b)
        cb.post("/friends/respond/", {"id": fr.id, "accept": "1"})
        self.assertTrue(social.are_friends(a, b))
        self.assertIn(b, list(social.friends_of(a)))
        self.assertIn(a, list(social.friends_of(b)))

    def test_reverse_request_auto_accepts(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/friends/request/", {"username": "bob"})
        # Bob requesting Alice back should accept the existing request.
        cb.post("/friends/request/", {"username": "alice"})
        self.assertTrue(social.are_friends(a, b))
        self.assertEqual(Friendship.objects.count(), 1)

    def test_remove_friendship(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        Friendship.objects.create(from_user=a, to_user=b, status=Friendship.ACCEPTED)
        ca.post("/friends/remove/", {"id": b.id})
        self.assertFalse(social.are_friends(a, b))

    def test_decline_request(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/friends/request/", {"username": "bob"})
        fr = Friendship.objects.get()
        cb.post("/friends/respond/", {"id": fr.id})  # no accept flag
        self.assertFalse(Friendship.objects.exists())


class SettingsTests(TestCase):
    def test_update_account_and_optin(self):
        c, u = _login("alice")
        c.post("/settings/account/", {"email": "a@x.com", "email_opt_in": "1"})
        u.refresh_from_db()
        self.assertEqual(u.email, "a@x.com")
        self.assertTrue(u.email_opt_in)
        c.post("/settings/account/", {"email": "a@x.com"})  # checkbox unchecked
        u.refresh_from_db()
        self.assertFalse(u.email_opt_in)

    def test_change_password(self):
        c, u = _login("alice")
        c.post("/settings/password/", {"current": "x", "new": "newpass"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("newpass"))
        # wrong current password is rejected
        c.post("/settings/password/", {"current": "wrong", "new": "another"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("newpass"))

    def test_delete_account_requires_password(self):
        c, u = _login("alice")
        c.post("/settings/delete/", {"password": "wrong"})
        self.assertTrue(User.objects.filter(pk=u.pk).exists())
        c.post("/settings/delete/", {"password": "x"})
        self.assertFalse(User.objects.filter(pk=u.pk).exists())

    def test_optout_blocks_email(self):
        from django.core import mail
        from billing.emails import send_receipt
        from django.utils import timezone
        from billing.models import Subscription
        _, u = _login("alice")
        u.email = "a@x.com"; u.email_opt_in = False; u.save()
        sub = Subscription(user=u, plan_code="gold_monthly", tier="gold",
                           provider="mock", current_period_end=timezone.now())
        mail.outbox = []
        send_receipt(u, sub)
        self.assertEqual(len(mail.outbox), 0)


class ChallengeTests(TestCase):
    def test_challenge_accept_creates_game(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/challenge/new/", {
            "opponent": "bob", "language": "es", "clock": "300,5", "rated": "1"})
        ch = Challenge.objects.get()
        self.assertEqual(ch.status, Challenge.PENDING)

        r = cb.post("/challenge/respond/", {"id": ch.id, "accept": "1"})
        self.assertEqual(r.status_code, 302)
        ch.refresh_from_db()
        self.assertEqual(ch.status, Challenge.ACCEPTED)
        self.assertIsNotNone(ch.game)
        game = ch.game
        self.assertEqual(game.status, Game.ACTIVE)
        self.assertEqual(game.clock_initial, 300)
        players = {s.player_id for s in game.seats}
        self.assertEqual(players, {a.id, b.id})

    def test_challenge_decline(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/challenge/new/", {"opponent": "bob", "language": "es", "clock": "0,0"})
        ch = Challenge.objects.get()
        cb.post("/challenge/respond/", {"id": ch.id})
        ch.refresh_from_db()
        self.assertEqual(ch.status, Challenge.DECLINED)
        self.assertFalse(Game.objects.exists())

    def test_cannot_challenge_self(self):
        ca, a = _login("alice")
        ca.post("/challenge/new/", {"opponent": "alice", "language": "es", "clock": "0,0"})
        self.assertFalse(Challenge.objects.exists())

    def test_guest_cannot_challenge(self):
        cb, b = _login("bob")
        guest = Client()
        guest.get("/")  # provisions a guest
        guest.post("/challenge/new/", {"opponent": "bob", "language": "es", "clock": "0,0"})
        self.assertFalse(Challenge.objects.exists())
