from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase

from accounts import social
from accounts.models import Friendship, Notification
from accounts.notifications import notify
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


class NotificationTests(TestCase):
    def test_notify_creates_record(self):
        _, u = _login("alice")
        notify(u, "hola", "/x/")
        self.assertEqual(Notification.objects.filter(user=u, text="hola").count(), 1)

    def test_guests_are_not_notified(self):
        g = User.objects.create(username="g1", is_guest=True)
        notify(g, "x")
        self.assertEqual(Notification.objects.count(), 0)

    def test_friend_request_notifies_target(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/friends/request/", {"username": "bob"})
        self.assertTrue(Notification.objects.filter(user=b).exists())

    def test_challenge_notifies_opponent(self):
        ca, a = _login("alice")
        cb, b = _login("bob")
        ca.post("/challenge/new/", {"opponent": "bob", "language": "es", "clock": "0,0"})
        self.assertTrue(Notification.objects.filter(user=b).exists())

    def test_inbox_marks_read(self):
        ca, a = _login("alice")
        notify(a, "uno")
        notify(a, "dos")
        self.assertEqual(Notification.objects.filter(user=a, is_read=False).count(), 2)
        ca.get("/notifications/")
        self.assertEqual(Notification.objects.filter(user=a, is_read=False).count(), 0)

    def test_correspondence_turn_notifies_opponent(self):
        from game import services
        a = User.objects.create_user("a", password="x")
        b = User.objects.create_user("b", password="x")
        game = services.join_game(services.create_game(a, rated=False), b)  # clockless
        c = Client(); c.force_login(a)
        c.post(f"/game/{game.id}/pass/")  # a's turn -> passes -> b's turn
        self.assertTrue(Notification.objects.filter(user=b).exists())

    def test_timed_game_does_not_notify_turn(self):
        from game import services
        a = User.objects.create_user("a", password="x")
        b = User.objects.create_user("b", password="x")
        game = services.join_game(
            services.create_game(a, rated=False, clock_initial=300), b)
        c = Client(); c.force_login(a)
        c.post(f"/game/{game.id}/pass/")
        self.assertFalse(Notification.objects.filter(user=b).exists())


class PasswordResetTests(TestCase):
    def test_reset_sends_email(self):
        from django.core import mail
        User.objects.create_user("resetme", password="x", email="r@example.com")
        mail.outbox = []
        r = Client().post("/password/reset/", {"email": "r@example.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset/", mail.outbox[0].body)

    def test_login_has_reset_link(self):
        self.assertContains(Client().get("/login/"), "/password/reset/")

    def test_auth_throttle_blocks_after_limit(self):
        from django.core.cache import cache
        from accounts.views import _auth_throttled
        cache.clear()
        rf = Client().get("/login/").wsgi_request
        hits = [_auth_throttled(rf, "probe") for _ in range(31)]
        self.assertFalse(hits[0])
        self.assertTrue(hits[-1])  # tripped within the window


class PresenceTests(TestCase):
    def test_touch_then_online_count(self):
        from django.core.cache import cache
        from accounts.presence import touch, online_count
        u = User.objects.create_user("on", password="x")
        bot = User.objects.create(username="IA-x", is_bot=True)
        from accounts.presence import touch as t
        t(bot)  # bots are excluded even if seen
        cache.clear()
        self.assertEqual(online_count(), 0)  # nobody human seen yet
        touch(u)
        cache.clear()
        self.assertEqual(online_count(), 1)

    def test_lobby_exposes_online_count(self):
        u = User.objects.create_user("p", password="x")
        # give the guest-less user a game so / shows the lobby, not the landing
        from game import services
        services.create_game(u, rated=False)
        c = Client(); c.force_login(u)
        self.assertIn("online_count", c.get("/").context)


class TournamentHistoryTests(TestCase):
    def test_profile_shows_arena_entry(self):
        from datetime import timedelta
        from django.utils import timezone
        from game.models import Arena, ArenaPlayer
        u = User.objects.create_user("champ", password="x")
        other = User.objects.create_user("rival", password="x")
        arena = Arena.objects.create(
            name="Winter Cup", starts_at=timezone.now() - timedelta(hours=2),
            duration_min=30)  # finished
        ArenaPlayer.objects.create(arena=arena, user=u, score=6, games=3)
        ArenaPlayer.objects.create(arena=arena, user=other, score=2, games=3)
        c = Client(); c.force_login(u)
        html = c.get(f"/@/{u.username}/").content.decode()
        self.assertIn("Winter Cup", html)
        self.assertIn("1", html)  # first place


class NotificationSocketTests(TransactionTestCase):
    async def test_live_push_received(self):
        from asgiref.sync import sync_to_async
        from channels.db import database_sync_to_async
        from channels.routing import URLRouter
        from channels.testing import WebsocketCommunicator
        from game.routing import websocket_urlpatterns

        user = await database_sync_to_async(User.objects.create)(username="sock")
        comm = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/notifications/")
        comm.scope["user"] = user
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await sync_to_async(notify)(user, "ping", "/p/")
        msg = await comm.receive_json_from(timeout=2)
        self.assertEqual(msg["text"], "ping")
        self.assertEqual(msg["url"], "/p/")
        await comm.disconnect()


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
        c.post("/settings/password/", {"current": "x", "new": "new-pass-1"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("new-pass-1"))
        # wrong current password is rejected
        c.post("/settings/password/", {"current": "wrong", "new": "another-1"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("new-pass-1"))

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
        guest.get("/puzzles/")  # provisions a guest ("/" doesn't)
        guest.post("/challenge/new/", {"opponent": "bob", "language": "es", "clock": "0,0"})
        self.assertFalse(Challenge.objects.exists())


class ClientIpTests(TestCase):
    """Limits count the address Traefik saw, the last X-Forwarded-For entry."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _ip(self, forwarded=None, remote="10.0.0.1"):
        from django.test import RequestFactory
        from game.ratelimit import client_ip
        extra = {"REMOTE_ADDR": remote}
        if forwarded is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded
        return client_ip(RequestFactory().get("/", **extra))

    def test_reads_the_entry_the_proxy_appended(self):
        self.assertEqual(self._ip("203.0.113.5"), "203.0.113.5")
        self.assertEqual(self._ip("9.9.9.9, 203.0.113.5"), "203.0.113.5")
        self.assertEqual(self._ip("9.9.9.9,8.8.8.8,203.0.113.5"), "203.0.113.5")

    def test_falls_back_to_the_peer(self):
        self.assertEqual(self._ip(), "10.0.0.1")
        self.assertEqual(self._ip(""), "10.0.0.1")
        self.assertEqual(self._ip("9.9.9.9, not-an-ip"), "10.0.0.1")

    def test_ipv6_counts_by_its_64(self):
        self.assertEqual(self._ip("2001:db8:1:2::1"), self._ip("2001:db8:1:2:ffff::9"))
        self.assertNotEqual(self._ip("2001:db8:1:2::1"), self._ip("2001:db8:1:3::1"))
        self.assertEqual(self._ip("::ffff:203.0.113.5"), "203.0.113.5")

    def test_one_client_cant_block_everybodys_login(self):
        def post(ip):
            return Client().post("/login/", {"username": "a", "password": "b"},
                                 HTTP_X_FORWARDED_FOR=ip)
        for _ in range(30):
            self.assertNotContains(post("203.0.113.5"), "Demasiados intentos")
        self.assertContains(post("203.0.113.5"), "Demasiados intentos")
        self.assertNotContains(post("203.0.113.6"), "Demasiados intentos")

    def test_rotating_the_header_buys_no_new_bucket(self):
        def post(i):
            return Client().post("/login/", {"username": "a", "password": "b"},
                                 HTTP_X_FORWARDED_FOR=f"9.9.9.{i}, 203.0.113.5")
        for i in range(30):
            self.assertNotContains(post(i), "Demasiados intentos")
        self.assertContains(post(99), "Demasiados intentos")

    def test_game_actions_of_visitors_count_per_client(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from django.http import JsonResponse
        from game.ratelimit import rate_limit

        @rate_limit("probe", limit=1, window=60)
        def view(request):
            return JsonResponse({"ok": True})

        def hit(ip):
            req = RequestFactory().post("/x", HTTP_X_FORWARDED_FOR=ip)
            req.user = AnonymousUser()
            return view(req).status_code

        self.assertEqual([hit("203.0.113.5"), hit("203.0.113.5")], [200, 429])
        self.assertEqual(hit("203.0.113.6"), 200)


class AdminLoginLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        User.objects.create_superuser("boss", password="boss-pass-1234")

    def _post(self, password, ip="203.0.113.5"):
        from django.urls import reverse
        return Client().post(reverse("admin:login"),
                             {"username": "boss", "password": password},
                             HTTP_X_FORWARDED_FOR=ip)

    def test_limited_per_client_even_with_the_right_password(self):
        for _ in range(10):
            self.assertEqual(self._post("wrong").status_code, 200)  # the form again
        self.assertEqual(self._post("wrong").status_code, 429)
        self.assertEqual(self._post("boss-pass-1234").status_code, 429)
        self.assertEqual(self._post("boss-pass-1234", ip="203.0.113.6").status_code, 302)

    def test_the_form_still_shows_and_works(self):
        from django.urls import reverse
        self.assertEqual(Client().get(reverse("admin:login")).status_code, 200)
        c = Client()
        r = c.post(reverse("admin:login"), {"username": "boss", "password": "boss-pass-1234",
                                            "next": reverse("admin:index")})
        self.assertRedirects(r, reverse("admin:index"))

    def test_csrf_still_applies(self):
        from django.urls import reverse
        r = Client(enforce_csrf_checks=True).post(
            reverse("admin:login"), {"username": "boss", "password": "boss-pass-1234"})
        self.assertEqual(r.status_code, 403)


class PasswordMinimumTests(TestCase):
    """Eight characters for any new password; accounts that already have a shorter one keep it."""

    def test_register(self):
        Client().post("/register/", {"username": "shorty", "password": "1234567"})
        self.assertFalse(User.objects.filter(username="shorty").exists())
        Client().post("/register/", {"username": "longer", "password": "12345678"})
        self.assertTrue(User.objects.filter(username="longer").exists())

    def test_change_password(self):
        c, u = _login("alice")
        r = c.post("/settings/password/", {"current": "x", "new": "1234567"}, follow=True)
        u.refresh_from_db()
        self.assertTrue(u.check_password("x"))
        self.assertIn("8", " ".join(str(m) for m in r.context["messages"]))
        c.post("/settings/password/", {"current": "x", "new": "12345678"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("12345678"))

    def test_password_reset(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        u = User.objects.create_user("resetme", password="old1")
        c = Client()
        url = f"/reset/{urlsafe_base64_encode(force_bytes(u.pk))}/{default_token_generator.make_token(u)}/"
        form_url = c.get(url).url
        c.post(form_url, {"new_password1": "1234567", "new_password2": "1234567"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("old1"))
        c.post(form_url, {"new_password1": "12345678", "new_password2": "12345678"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("12345678"))

    def test_an_existing_short_password_still_logs_in(self):
        User.objects.create_user("old", password="abcd")
        c = Client()
        r = c.post("/login/", {"username": "old", "password": "abcd"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(c.session["_auth_user_id"]), User.objects.get(username="old").pk)


class GuestProvisioningTests(TestCase):
    """The landing creates no guest; the first real action still does."""

    def test_landing_creates_no_guest(self):
        before = User.objects.count()
        for _ in range(3):  # a health check / uptime monitor / crawler
            r = Client().get("/")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), before)

    def test_other_pages_still_provision_a_guest(self):
        c = Client()
        c.get("/puzzles/")
        self.assertTrue(User.objects.get(pk=c.session["_auth_user_id"]).is_guest)

    def test_play_from_the_landing_passes_csrf_and_logs_in_a_guest(self):
        # The guest is created (and the CSRF token rotated by login) on the
        # POST itself: Django checks the token against the original cookie.
        c = Client(enforce_csrf_checks=True)
        token = str(c.get("/").context["csrf_token"])
        r = c.post("/play/", {"csrfmiddlewaretoken": token, "language": "es", "clock": "0,0"})
        self.assertNotEqual(r.status_code, 403)
        self.assertTrue(User.objects.get(pk=c.session["_auth_user_id"]).is_guest)


class BotIdentityTests(TestCase):
    """Bots are found by flag and level, never by a name someone can register."""

    def test_register_rejects_bot_names(self):
        before = User.objects.filter(is_guest=False).count()
        for name in ["IA-Experta", "ia-experta", "IA-Nueva", "ＩＡ-Experta",
                     "ІА-Experta"]:  # full-width; Cyrillic look-alikes
            r = Client().post("/register/", {"username": name, "password": "secreto1"})
            self.assertEqual(r.status_code, 200, name)  # form re-rendered with the error
        self.assertEqual(User.objects.filter(is_guest=False).count(), before)

    def test_guest_cannot_upgrade_into_a_bot_name(self):
        guest = User.objects.create(username="guest_x", is_guest=True)
        c = Client()
        c.force_login(guest)
        c.post("/register/", {"username": "IA-Difícil", "password": "secreto1"})
        guest.refresh_from_db()
        self.assertTrue(guest.is_guest)
        self.assertEqual(guest.username, "guest_x")

    def test_ordinary_names_still_register(self):
        r = Client().post("/register/", {"username": "Iara-ok", "password": "secreto1"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="Iara-ok", is_bot=False).exists())

    def test_person_named_like_a_bot_is_never_the_ai(self):
        from game import services
        User.objects.filter(is_bot=True).delete()
        squatter = User.objects.create_user("IA-Experta", password="x")
        human = User.objects.create_user("human", password="x")

        game = services.create_ai_game(human, level="expert", language="es")
        opponent = game.players.exclude(player=human).get().player
        self.assertNotEqual(opponent.pk, squatter.pk)
        self.assertTrue(opponent.is_bot)
        self.assertEqual(opponent.bot_level, "expert")
        self.assertEqual(opponent.username, "IA-Experta-bot")
        self.assertEqual(opponent.display_name, "IA-Experta")
        squatter.refresh_from_db()
        self.assertFalse(squatter.is_bot)
        # The same bot account is reused for the next game.
        game2 = services.create_ai_game(human, level="expert", language="es")
        self.assertEqual(game2.players.exclude(player=human).get().player_id, opponent.pk)

    def test_bots_exist_after_migrate(self):
        from accounts.bots import BOT_LEVELS
        levels = set(User.objects.filter(is_bot=True).exclude(bot_level="")
                     .values_list("bot_level", flat=True))
        self.assertEqual(levels, set(BOT_LEVELS))

    def test_data_migration_tags_legacy_bot_and_spares_people(self):
        import importlib
        from django.apps import apps
        mig = importlib.import_module("accounts.migrations.0010_create_bots")

        User.objects.filter(is_bot=True).delete()
        legacy = User.objects.create(username="IA-Media", is_bot=True, rating=1450)
        person = User.objects.create_user("IA-Experta", password="x")

        mig.create_bots(apps, None)
        mig.create_bots(apps, None)  # idempotent

        legacy.refresh_from_db()
        self.assertEqual(legacy.bot_level, "medium")
        self.assertEqual(legacy.rating, 1450)
        person.refresh_from_db()
        self.assertFalse(person.is_bot)
        self.assertEqual(person.bot_level, "")
        expert = User.objects.get(is_bot=True, bot_level="expert")
        self.assertEqual(expert.username, "IA-Experta-bot")
        self.assertFalse(expert.has_usable_password())
        self.assertEqual(User.objects.filter(is_bot=True).exclude(bot_level="").count(), 5)
        self.assertEqual(User.objects.get(is_bot=True, bot_level="hard").username, "IA-Difícil")
