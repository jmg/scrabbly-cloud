from django.test import TestCase, TransactionTestCase

from .engine import (
    DISTRIBUTIONS,
    Bag,
    Board,
    InvalidMove,
    Placement,
    WordList,
    get_ruleset,
    validate_and_score,
)
from . import ratings


class EngineTests(TestCase):
    def test_first_move_must_cross_center(self):
        board = Board()
        # CASA placed off-center should be rejected.
        placements = [Placement("C", 0, 0), Placement("A", 0, 1),
                      Placement("S", 0, 2), Placement("A", 0, 3)]
        with self.assertRaises(InvalidMove):
            validate_and_score(board, placements)

    def test_first_move_scores_with_center_double(self):
        board = Board()
        # CASA across the center row: C(7,6) A(7,7)* S(7,8) A(7,9)
        placements = [Placement("C", 7, 6), Placement("A", 7, 7),
                      Placement("S", 7, 8), Placement("A", 7, 9)]
        result = validate_and_score(board, placements)
        # C3 A1 S1 A1 = 6, center is double word -> 12.
        self.assertEqual(result.points, 12)
        self.assertEqual(result.words[0][0], "CASA")

    def test_blank_scores_zero(self):
        board = Board()
        placements = [Placement("C", 7, 6), Placement("A", 7, 7, is_blank=True),
                      Placement("S", 7, 8), Placement("A", 7, 9)]
        result = validate_and_score(board, placements)
        # (3 + 0 + 1 + 1) * 2 = 10
        self.assertEqual(result.points, 10)

    def test_bingo_bonus(self):
        board = Board()
        placements = [Placement(l, 7, 4 + i) for i, l in enumerate("CASEROS")]
        result = validate_and_score(board, placements)
        self.assertGreaterEqual(result.points, 50)

    def test_disconnected_second_move_rejected(self):
        board = Board(grid={(7, 7): "A"})
        placements = [Placement("S", 0, 0), Placement("I", 0, 1)]
        with self.assertRaises(InvalidMove):
            validate_and_score(board, placements)

    def test_wordlist_rejects_invalid(self):
        wl = WordList(["CASA", "SOL"])
        board = Board()
        placements = [Placement("X", 7, 7), Placement("Z", 7, 8)]
        with self.assertRaises(InvalidMove):
            validate_and_score(board, placements, wl)

    def test_bag_draws_and_depletes(self):
        bag = Bag()
        self.assertEqual(len(bag), 100)
        drawn = bag.draw(7)
        self.assertEqual(len(drawn), 7)
        self.assertEqual(len(bag), 93)


class LanguageTests(TestCase):
    def test_both_distributions_have_100_tiles(self):
        for code, dist in DISTRIBUTIONS.items():
            self.assertEqual(sum(c for c, _ in dist.values()), 100, code)

    def test_english_scoring_differs_from_spanish(self):
        # H is worth 4 in Spanish but 4 in English too; use C (3 es / 3 en) ->
        # use W which only exists in English (4 points).
        en = get_ruleset("en")
        es = get_ruleset("es")
        self.assertEqual(en.points["W"], 4)
        self.assertNotIn("W", es.points)
        self.assertEqual(es.points["Ñ"], 8)
        self.assertNotIn("Ñ", en.points)

    def test_english_word_scored_with_english_values(self):
        board = Board()
        ruleset = get_ruleset("en")
        # WORD across center: W(7,6) O(7,7)* R(7,8) D(7,9) = (4+1+1+2)*2 = 16
        placements = [Placement("W", 7, 6), Placement("O", 7, 7),
                      Placement("R", 7, 8), Placement("D", 7, 9)]
        result = validate_and_score(board, placements, ruleset=ruleset)
        self.assertEqual(result.points, 16)
        self.assertEqual(result.words[0][0], "WORD")

    def test_gzip_dictionary_validates(self):
        from django.conf import settings
        from .services import get_wordlist
        get_wordlist.__globals__["_wordlists"] = {}  # reset cache
        wl_en = get_wordlist("en")
        if wl_en.enabled:  # dictionaries shipped
            self.assertTrue(wl_en.is_valid("WORD"))
            self.assertFalse(wl_en.is_valid("ZZZZZ"))
            wl_es = get_wordlist("es")
            self.assertTrue(wl_es.is_valid("CASA"))


class ClockTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.u1 = User.objects.create(username="p1")
        self.u2 = User.objects.create(username="p2")

    def _timed_active_game(self, initial=300, increment=5):
        from game import services
        g = services.create_game(self.u1, clock_initial=initial,
                                  clock_increment=increment)
        g = services.join_game(g, self.u2)
        return g

    def test_clock_starts_when_game_becomes_active(self):
        g = self._timed_active_game()
        self.assertEqual(g.status, "active")
        self.assertIsNotNone(g.turn_started_at)
        for s in g.players.all():
            self.assertEqual(s.time_left_ms, 300 * 1000)

    def test_pass_charges_time_and_adds_increment(self):
        import datetime
        from django.utils import timezone
        from game import services
        from game.models import Game
        g = self._timed_active_game(initial=300, increment=5)
        # Pretend the player on move started their turn 10s ago.
        Game.objects.filter(pk=g.pk).update(
            turn_started_at=timezone.now() - datetime.timedelta(seconds=10)
        )
        g.refresh_from_db()
        mover = g.current_seat.player
        services.make_pass(g, mover)
        g.refresh_from_db()
        seat = g.players.get(player=mover)
        # 300s - ~10s + 5s increment ≈ 295s. Allow slack for execution time.
        self.assertLess(seat.time_left_ms, 300 * 1000)
        self.assertGreater(seat.time_left_ms, 293 * 1000)

    def test_claim_time_flags_expired_player(self):
        import datetime
        from django.utils import timezone
        from game import services
        from game.models import Game
        from game.engine import InvalidMove
        g = self._timed_active_game(initial=5, increment=0)
        opponent = g.players.exclude(player=g.current_seat.player).first().player
        # Not expired yet -> claim should fail.
        with self.assertRaises(InvalidMove):
            services.claim_time(g, opponent)
        # Force the clock to have started 10s ago (> 5s budget).
        Game.objects.filter(pk=g.pk).update(
            turn_started_at=timezone.now() - datetime.timedelta(seconds=10)
        )
        g.refresh_from_db()
        flagged_player = g.current_seat.player
        services.claim_time(g, opponent)
        g.refresh_from_db()
        self.assertEqual(g.status, "finished")
        self.assertEqual(g.winner_id, opponent.pk)
        self.assertNotEqual(g.winner_id, flagged_player.pk)


class DrawRematchTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from game import services
        self.u1 = User.objects.create(username="d1")
        self.u2 = User.objects.create(username="d2")
        g = services.create_game(self.u1, rated=True)
        self.game = services.join_game(g, self.u2)

    def test_draw_offer_and_accept_ends_in_draw(self):
        from game import services
        from game.models import GamePlayer
        services.offer_draw(self.game, self.u1)
        self.game.refresh_from_db()
        self.assertEqual(self.game.draw_offer_by_id, self.u1.pk)
        services.respond_draw(self.game, self.u2, accept=True)
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, "finished")
        self.assertIsNone(self.game.winner_id)
        for s in self.game.players.all():
            self.assertEqual(s.result, GamePlayer.DRAW)

    def test_cannot_accept_own_draw_offer(self):
        from game import services
        from game.engine import InvalidMove
        services.offer_draw(self.game, self.u1)
        with self.assertRaises(InvalidMove):
            services.respond_draw(self.game, self.u1, accept=True)

    def test_decline_draw_clears_offer(self):
        from game import services
        services.offer_draw(self.game, self.u1)
        services.respond_draw(self.game, self.u2, accept=False)
        self.game.refresh_from_db()
        self.assertIsNone(self.game.draw_offer_by_id)
        self.assertEqual(self.game.status, "active")

    def test_rematch_offer_and_accept_creates_swapped_game(self):
        from game import services
        services.resign(self.game, self.u1)  # finish the game
        services.offer_rematch(self.game, self.u1)
        self.game.refresh_from_db()
        self.assertEqual(self.game.rematch_offer_by_id, self.u1.pk)
        services.offer_rematch(self.game, self.u2)  # acceptance
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.next_game_id)
        new = self.game.next_game
        self.assertEqual(new.status, "active")
        # Seats are swapped: previous second player opens the rematch.
        self.assertEqual(new.seats[0].player_id, self.u2.pk)
        self.assertEqual(new.seats[1].player_id, self.u1.pk)


class FinishTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from game import services
        self.u1 = User.objects.create(username="f1")
        self.u2 = User.objects.create(username="f2")
        g = services.create_game(self.u1, rated=False)
        self.game = services.join_game(g, self.u2)

    def test_resigner_loses_opponent_wins(self):
        from game import services
        from game.models import GamePlayer
        resigner = self.game.current_seat.player
        opponent = self.game.players.exclude(player=resigner).first().player
        services.resign(self.game, resigner)
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, "finished")
        self.assertEqual(self.game.winner_id, opponent.pk)
        self.assertEqual(
            self.game.players.get(player=resigner).result, GamePlayer.LOSS)
        self.assertEqual(
            self.game.players.get(player=opponent).result, GamePlayer.WIN)


class ConsumerTests(TransactionTestCase):
    """Integration tests for the live game WebSocket."""

    def _make_game(self):
        from accounts.models import User
        from game import services
        u1 = User.objects.create(username="w1")
        u2 = User.objects.create(username="w2")
        g = services.create_game(u1, rated=False)
        return services.join_game(g, u2)

    async def _connect(self, game_id):
        from channels.routing import URLRouter
        from channels.testing import WebsocketCommunicator
        from game.routing import websocket_urlpatterns
        app = URLRouter(websocket_urlpatterns)
        comm = WebsocketCommunicator(app, f"/ws/game/{game_id}/")
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        return comm

    async def test_connect_pushes_initial_state(self):
        from channels.db import database_sync_to_async
        game = await database_sync_to_async(self._make_game)()
        comm = await self._connect(game.pk)
        msg = await comm.receive_json_from(timeout=2)
        self.assertEqual(msg["type"], "state")
        self.assertEqual(msg["state"]["id"], game.pk)
        self.assertEqual(len(msg["state"]["players"]), 2)
        await comm.disconnect()

    async def test_update_is_broadcast_to_watchers(self):
        from channels.db import database_sync_to_async
        from asgiref.sync import sync_to_async
        from game.realtime import notify_update
        game = await database_sync_to_async(self._make_game)()
        comm = await self._connect(game.pk)
        await comm.receive_json_from(timeout=2)  # initial state
        # A server-side notify should push a fresh state to the socket.
        await sync_to_async(notify_update)(game.pk)
        msg = await comm.receive_json_from(timeout=2)
        self.assertEqual(msg["type"], "state")
        await comm.disconnect()


class LobbyTests(TestCase):
    def test_correspondence_split_your_move_vs_waiting(self):
        from django.test import Client
        from accounts.models import User
        from game import services

        c1, c2 = Client(), Client()
        c1.get("/")
        c2.get("/")
        u1 = User.objects.get(pk=c1.session["_auth_user_id"])
        gid = c1.post("/game/quick/", {"clock": "0,0"}).url.split("/")[-2]
        c2.post("/game/quick/", {"clock": "0,0"})

        # Seat 0 (the creator, u1) is on the move.
        r1 = c1.get("/")
        self.assertEqual(len(r1.context["my_turn"]), 1)
        self.assertEqual(len(r1.context["my_waiting"]), 0)
        # The opponent is waiting, not on the move.
        r2 = c2.get("/")
        self.assertEqual(len(r2.context["my_turn"]), 0)
        self.assertEqual(len(r2.context["my_waiting"]), 1)

        # After u1 passes, it flips: now the opponent is on the move.
        from game.models import Game
        services.make_pass(Game.objects.get(pk=gid), u1)
        self.assertEqual(len(c1.get("/").context["my_turn"]), 0)
        self.assertEqual(len(c2.get("/").context["my_turn"]), 1)


class ApiTests(TestCase):
    def test_public_endpoints(self):
        from django.test import Client
        from accounts.models import User
        from game import services
        u1 = User.objects.create_user(username="api1", password="xxxx")
        u2 = User.objects.create(username="api2")
        guest = User.objects.create(username="g_x", is_guest=True)
        g = services.join_game(services.create_game(u1), u2)
        c = Client()

        r = c.get("/api/games/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(item["id"] == g.pk for item in r.json()["games"]))

        r = c.get(f"/api/games/{g.pk}/")
        self.assertEqual(r.json()["id"], g.pk)
        self.assertEqual(len(r.json()["players"]), 2)

        self.assertEqual(c.get("/api/leaderboard/").status_code, 200)

        r = c.get("/api/players/api1/")
        self.assertEqual(r.json()["username"], "api1")
        # Guest accounts are not exposed by the player endpoint.
        self.assertEqual(c.get(f"/api/players/{guest.username}/").status_code, 404)

    def test_api_does_not_create_guest_users(self):
        from django.test import Client
        from accounts.models import User
        before = User.objects.count()
        Client().get("/api/games/")
        self.assertEqual(User.objects.count(), before)


class RateLimitTests(TestCase):
    def test_blocks_after_limit(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from django.core.cache import cache
        from django.http import JsonResponse
        from game.ratelimit import rate_limit

        cache.clear()
        calls = {"n": 0}

        @rate_limit("test", limit=2, window=60)
        def view(request):
            calls["n"] += 1
            return JsonResponse({"ok": True})

        rf = RequestFactory()

        def hit():
            req = rf.post("/x")
            req.user = AnonymousUser()
            return view(req)

        self.assertEqual(hit().status_code, 200)
        self.assertEqual(hit().status_code, 200)
        self.assertEqual(hit().status_code, 429)  # third call is throttled
        self.assertEqual(calls["n"], 2)


class AvatarTests(TestCase):
    def test_avatar_is_deterministic_svg(self):
        from accounts.templatetags.avatars import avatar
        a = avatar("alice", 40)
        self.assertIn("<svg", a)
        self.assertEqual(avatar("alice", 40), a)
        self.assertNotEqual(avatar("alice", 40), avatar("bob", 40))


class RatingTests(TestCase):
    def test_winner_gains_loser_loses(self):
        new = ratings.compute_updates([
            {"rating": 1500, "points": 300},
            {"rating": 1500, "points": 200},
        ])
        self.assertGreater(new[0], 1500)
        self.assertLess(new[1], 1500)
        self.assertEqual(new[0] - 1500, 1500 - new[1])

    def test_draw_is_neutral_for_equal_ratings(self):
        new = ratings.compute_updates([
            {"rating": 1500, "points": 200},
            {"rating": 1500, "points": 200},
        ])
        self.assertEqual(new, [1500, 1500])
