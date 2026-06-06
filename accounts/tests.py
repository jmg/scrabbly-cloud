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
