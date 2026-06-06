"""Game orchestration: ties the engine, models and ratings together.

All mutating operations run inside a transaction and return the updated Game.
Turn/seat enforcement lives here so both HTTP views and the WebSocket consumer
share one source of truth.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User

from . import ratings
import os

from .engine import (
    BLANK,
    DEFAULT_LANGUAGE,
    RACK_SIZE,
    Bag,
    Board,
    InvalidMove,
    Placement,
    WordList,
    get_ruleset,
    validate_and_score,
)
from .models import Game, GamePlayer, Move

_wordlists = {}


def get_wordlist(language):
    """Return the (cached) WordList for a language, loading from disk on first use."""
    if language not in _wordlists:
        directory = getattr(settings, "SCRABBLE_DICTIONARY_DIR", "")
        wl = WordList()
        if directory:
            for candidate in (f"{language}.txt.gz", f"{language}.txt"):
                path = os.path.join(directory, candidate)
                if os.path.exists(path):
                    wl = WordList.from_file(path)
                    break
        _wordlists[language] = wl
    return _wordlists[language]


def _draw_for(game, seat, bag):
    need = RACK_SIZE - len(seat.rack)
    if need > 0:
        seat.rack = list(seat.rack) + bag.draw(need)


def _check_game_quota(user):
    """Free accounts may only have a limited number of games in progress."""
    from accounts.models import FREE_CONCURRENT_GAMES

    if getattr(user, "is_premium", False):
        return
    in_progress = (
        Game.objects.filter(players__player=user)
        .filter(status__in=[Game.WAITING, Game.ACTIVE])
        .distinct()
        .count()
    )
    if in_progress >= FREE_CONCURRENT_GAMES:
        raise InvalidMove(
            f"Las cuentas gratuitas pueden tener hasta {FREE_CONCURRENT_GAMES} "
            "partidas a la vez. Pasate a Premium para partidas ilimitadas."
        )


def create_game(user, rated=True, max_players=2, language=DEFAULT_LANGUAGE,
                clock_initial=0, clock_increment=0):
    with transaction.atomic():
        _check_game_quota(user)
        bag = get_ruleset(language).new_bag()
        game = Game.objects.create(
            status=Game.WAITING, rated=rated, max_players=max_players,
            language=language, board=Board().serialize(), bag=bag.letters,
            clock_initial=clock_initial, clock_increment=clock_increment,
        )
        seat = GamePlayer.objects.create(
            game=game, player=user, seat=0,
            time_left_ms=clock_initial * 1000,
        )
        _draw_for(game, seat, bag)
        seat.save()
        game.bag = bag.letters
        game.save(update_fields=["bag"])
    return game


def _start_clock(game):
    """Begin the active player's clock when the game becomes active."""
    if game.has_clock:
        game.turn_started_at = timezone.now()


def join_game(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        existing = game.seat_for(user)
        if existing:
            return game
        if game.status != Game.WAITING or game.is_full:
            raise InvalidMove("La partida ya no admite jugadores.")
        _check_game_quota(user)
        bag = Bag(letters=list(game.bag))
        seat = GamePlayer.objects.create(
            game=game, player=user, seat=game.players.count(),
            time_left_ms=game.clock_initial * 1000,
        )
        _draw_for(game, seat, bag)
        seat.save()
        game.bag = bag.letters
        if game.is_full:
            game.status = Game.ACTIVE
            _start_clock(game)
        game.save()
    return game


def quick_pair(user, rated=True, language=DEFAULT_LANGUAGE,
               clock_initial=0, clock_increment=0):
    """Join the oldest compatible waiting game, or open a new one.

    Compatibility means same language and identical time control.
    """
    with transaction.atomic():
        candidate = (
            Game.objects.select_for_update(skip_locked=True)
            .filter(status=Game.WAITING, rated=rated, language=language,
                    clock_initial=clock_initial, clock_increment=clock_increment)
            .exclude(players__player=user)
            .order_by("created_at")
            .first()
        )
    if candidate:
        return join_game(candidate, user)
    return create_game(user, rated=rated, language=language,
                       clock_initial=clock_initial, clock_increment=clock_increment)


def _consume_from_rack(rack, placements):
    """Remove the letters used by ``placements`` from a rack copy.

    Blanks are taken as BLANK tiles. Returns the new rack or raises InvalidMove.
    """
    rack = list(rack)
    for p in placements:
        needed = BLANK if p.is_blank else p.letter
        if needed not in rack:
            raise InvalidMove("No tenés esas fichas en tu atril.")
        rack.remove(needed)
    return rack


def _advance_turn(game):
    n = game.players.count()
    game.turn_index = (game.turn_index + 1) % n


def _charge_clock(game, seat):
    """Deduct the time the seat spent on the turn that just ended.

    Adds the Fischer increment and restarts the clock for the next player.
    Returns True if the seat ran out of time (flagged) during this turn.
    """
    if not game.has_clock or game.turn_started_at is None:
        return False
    now = timezone.now()
    elapsed_ms = int((now - game.turn_started_at).total_seconds() * 1000)
    seat.time_left_ms -= elapsed_ms
    game.turn_started_at = now
    if seat.time_left_ms <= 0:
        seat.time_left_ms = 0
        return True
    seat.time_left_ms += game.clock_increment * 1000
    return False


def make_play(game, user, placements_data):
    """placements_data: list of {letter, row, col, is_blank}."""
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = _require_turn(game, user)
        game.draw_offer_by = None

        placements = [
            Placement(
                letter=str(d["letter"]).upper(),
                row=int(d["row"]), col=int(d["col"]),
                is_blank=bool(d.get("is_blank")),
            )
            for d in placements_data
        ]
        ruleset = get_ruleset(game.language)
        board = Board.deserialize(game.board)
        result = validate_and_score(
            board, placements, get_wordlist(game.language), ruleset
        )

        seat.rack = _consume_from_rack(seat.rack, placements)
        board.apply(placements)
        bag = Bag(letters=list(game.bag))
        _draw_for(game, seat, bag)

        seat.score += result.points
        flagged = _charge_clock(game, seat)
        seat.save()

        game.board = board.serialize()
        game.bag = bag.letters
        game.consecutive_passes = 0
        _record_move(game, user, Move.PLAY, placements_data, result.words, result.points)

        if flagged:
            _finish(game, loser=seat)
        elif len(seat.rack) == 0 and len(bag) == 0:
            _finish(game, last_seat=seat)
        else:
            _advance_turn(game)
            game.save()
    return game


def make_pass(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = _require_turn(game, user)
        game.draw_offer_by = None
        game.consecutive_passes += 1
        flagged = _charge_clock(game, seat)
        seat.save()
        _record_move(game, user, Move.PASS, [], [], 0)
        if flagged:
            _finish(game, loser=seat)
        # End if everyone passed twice in a row.
        elif game.consecutive_passes >= 2 * game.players.count():
            _finish(game)
        else:
            _advance_turn(game)
            game.save()
    return game


def make_exchange(game, user, letters):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = _require_turn(game, user)
        game.draw_offer_by = None
        bag = Bag(letters=list(game.bag))
        if len(bag) < len(letters):
            raise InvalidMove("No hay suficientes fichas en la bolsa.")
        rack = list(seat.rack)
        for letter in letters:
            if letter not in rack:
                raise InvalidMove("No tenés esas fichas.")
            rack.remove(letter)
        drawn = bag.draw(len(letters))
        bag.put_back(letters)
        seat.rack = rack + drawn
        flagged = _charge_clock(game, seat)
        seat.save()
        game.bag = bag.letters
        game.consecutive_passes = 0
        _record_move(game, user, Move.EXCHANGE, [], [], 0)
        if flagged:
            _finish(game, loser=seat)
        else:
            _advance_turn(game)
            game.save()
    return game


def resign(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = game.seat_for(user)
        if not seat or game.status not in (Game.WAITING, Game.ACTIVE):
            raise InvalidMove("No podés abandonar esta partida.")
        _record_move(game, user, Move.RESIGN, [], [], 0)
        others = list(game.players.exclude(pk=seat.pk))
        if game.status == Game.WAITING or not others:
            game.status = Game.ABORTED
            game.save()
        else:
            # Resigning player ranks last; pick highest scorer as winner.
            _finish(game, loser=seat)
    return game


def offer_draw(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = game.seat_for(user)
        if not seat or game.status != Game.ACTIVE:
            raise InvalidMove("No podés ofrecer tablas ahora.")
        # If the opponent already offered, this acts as an acceptance.
        if game.draw_offer_by_id and game.draw_offer_by_id != user.pk:
            _finish(game, forced_draw=True)
            return game
        game.draw_offer_by = user
        game.save(update_fields=["draw_offer_by"])
    return game


def respond_draw(game, user, accept):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = game.seat_for(user)
        if not seat or game.status != Game.ACTIVE or not game.draw_offer_by_id:
            raise InvalidMove("No hay oferta de tablas pendiente.")
        if game.draw_offer_by_id == user.pk:
            raise InvalidMove("No podés responder tu propia oferta.")
        if accept:
            _finish(game, forced_draw=True)
        else:
            game.draw_offer_by = None
            game.save(update_fields=["draw_offer_by"])
    return game


def offer_rematch(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = game.seat_for(user)
        if not seat or game.status not in (Game.FINISHED, Game.ABORTED):
            raise InvalidMove("Solo se puede pedir revancha al terminar.")
        if game.players.count() != 2:
            raise InvalidMove("La revancha es solo para partidas de dos.")
        if game.next_game_id:
            return game
        # If the opponent already offered, accept and build the rematch.
        if game.rematch_offer_by_id and game.rematch_offer_by_id != user.pk:
            return _create_rematch(game)
        game.rematch_offer_by = user
        game.save(update_fields=["rematch_offer_by"])
    return game


def _create_rematch(game):
    """Spawn a fresh game with the same settings and swapped seat order."""
    seats = list(game.seats)
    # Swap who starts: previous second seat opens the rematch.
    first, second = seats[1].player, seats[0].player
    new_game = create_game(
        first, rated=game.rated, language=game.language,
        clock_initial=game.clock_initial, clock_increment=game.clock_increment,
    )
    new_game = join_game(new_game, second)
    game.next_game = new_game
    game.rematch_offer_by = None
    game.save(update_fields=["next_game", "rematch_offer_by"])
    return game


def claim_time(game, user):
    """Flag the player on the move if their clock has expired.

    Callable by anyone watching the game (typically the opponent whose UI saw
    the clock hit zero). Server-side time is authoritative.
    """
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        if game.status != Game.ACTIVE or not game.has_clock:
            raise InvalidMove("No hay reloj que reclamar.")
        seat = game.current_seat
        if seat is None or game.turn_started_at is None:
            raise InvalidMove("No se puede reclamar el tiempo.")
        elapsed_ms = int((timezone.now() - game.turn_started_at).total_seconds() * 1000)
        if seat.time_left_ms - elapsed_ms > 0:
            raise InvalidMove("Al jugador todavía le queda tiempo.")
        seat.time_left_ms = 0
        seat.save()
        _finish(game, loser=seat)
    return game


def _require_turn(game, user):
    if game.status != Game.ACTIVE:
        raise InvalidMove("La partida no está activa.")
    seat = game.current_seat
    if seat is None or seat.player_id != user.pk:
        raise InvalidMove("No es tu turno.")
    return seat


def _record_move(game, user, kind, placements, words, points):
    number = game.moves.count() + 1
    Move.objects.create(
        game=game, player=user, number=number, kind=kind,
        placements=placements, words=words, points=points,
    )


def _rack_value(rack, ruleset):
    return sum(ruleset.letter_points(letter, letter == BLANK) for letter in rack)


def _finish(game, last_seat=None, loser=None, forced_draw=False):
    """Apply end-of-game scoring and rating changes, then mark finished."""
    seats = list(game.players.all())
    ruleset = get_ruleset(game.language)
    # `loser`/`last_seat` may be instances fetched elsewhere; match them to the
    # freshly-loaded seat objects by pk so identity checks are reliable.
    loser_pk = loser.pk if loser else None
    last_pk = last_seat.pk if last_seat else None

    # Endgame tile adjustment: each player loses their remaining rack value; if
    # someone emptied their rack, they also gain the sum of everyone else's.
    leftover_total = 0
    for seat in seats:
        value = _rack_value(seat.rack, ruleset)
        seat.score -= value
        leftover_total += value
    if last_pk is not None:
        for seat in seats:
            if seat.pk == last_pk:
                seat.score += leftover_total

    # Determine winner. A resigning/flagged player is forced last.
    if forced_draw:
        game.winner = None
    else:
        ranked = sorted(
            seats,
            key=lambda s: (-1 if s.pk == loser_pk else 0, s.score),
            reverse=True,
        )
        top_score = ranked[0].score
        winners = [s for s in ranked if s.score == top_score and s.pk != loser_pk]
        is_draw = len(winners) != 1
        game.winner = None if is_draw else winners[0].player

    _apply_ratings(game, seats, loser_pk, forced_draw)

    for seat in seats:
        seat.save()
    for seat in seats:
        _update_stats(seat)

    game.status = Game.FINISHED
    game.save()


def _apply_ratings(game, seats, loser_pk, forced_draw=False):
    if not game.rated:
        for seat in seats:
            if seat.result == "":
                _set_result(seat, loser_pk, forced_draw)
        return
    standings = [
        {"rating": seat.player.rating,
         "points": 0 if forced_draw else (-1 if seat.pk == loser_pk else seat.score)}
        for seat in seats
    ]
    new_ratings = ratings.compute_updates(standings)
    for seat, new_rating in zip(seats, new_ratings):
        seat.rating_before = seat.player.rating
        seat.rating_after = new_rating
        seat.player.rating = new_rating
        seat.player.save(update_fields=["rating"])
        _set_result(seat, loser_pk, forced_draw)


def _set_result(seat, loser_pk, forced_draw=False):
    game = seat.game
    if forced_draw:
        seat.result = GamePlayer.DRAW
        return
    if seat.pk == loser_pk:
        seat.result = GamePlayer.LOSS
    elif game.winner_id is None:
        seat.result = GamePlayer.DRAW
    elif game.winner_id == seat.player_id:
        seat.result = GamePlayer.WIN
    else:
        seat.result = GamePlayer.LOSS


def _update_stats(seat):
    player = seat.player
    player.games_played += 1
    if seat.result == GamePlayer.WIN:
        player.wins += 1
    elif seat.result == GamePlayer.LOSS:
        player.losses += 1
    elif seat.result == GamePlayer.DRAW:
        player.draws += 1
    player.save(update_fields=["games_played", "wins", "losses", "draws"])


# ---------------------------------------------------------------------------
# Serialization for the client (HTTP bootstrap + WebSocket broadcasts).
# ---------------------------------------------------------------------------

def public_state(game):
    board = Board.deserialize(game.board)
    current = game.current_seat
    ruleset = get_ruleset(game.language)
    return {
        "id": game.pk,
        "status": game.status,
        "rated": game.rated,
        "language": game.language,
        "points": ruleset.points,
        "turn_user_id": current.player_id if current and game.status == Game.ACTIVE else None,
        "bag_count": len(game.bag),
        "winner_id": game.winner_id,
        "draw_offer_by": game.draw_offer_by_id,
        "rematch": {
            "offer_by": game.rematch_offer_by_id,
            "next_game_id": game.next_game_id,
        },
        "clock": {
            "enabled": game.has_clock,
            "initial": game.clock_initial,
            "increment": game.clock_increment,
            # Epoch millis so the client can run a live countdown for the
            # player on the move, corrected against server time.
            "turn_started_at": (
                int(game.turn_started_at.timestamp() * 1000)
                if game.turn_started_at and game.status == Game.ACTIVE else None
            ),
            "server_now": int(timezone.now().timestamp() * 1000),
        },
        "grid": [
            {"row": r, "col": c, "letter": letter,
             "blank": [r, c] in [list(b) for b in board.blanks]}
            for (r, c), letter in board.grid.items()
        ],
        "players": [
            {
                "user_id": s.player_id,
                "name": s.player.display_name,
                "rating": s.player.rating,
                "premium": s.player.is_premium,
                "tier": s.player.tier,
                "seat": s.seat,
                "score": s.score,
                "tiles_left": len(s.rack),
                "result": s.result,
                "rating_delta": s.rating_delta,
                "time_left_ms": s.time_left_ms if game.has_clock else None,
            }
            for s in game.seats
        ],
        "moves": [
            {
                "number": m.number,
                "player": m.player.display_name,
                "kind": m.kind,
                "words": m.words,
                "points": m.points,
                "placements": m.placements,
            }
            for m in game.moves.select_related("player")
        ],
    }


def rack_for(game, user):
    seat = game.seat_for(user)
    return list(seat.rack) if seat else []


def game_analysis(game):
    """Per-player breakdown of a finished game (premium feature)."""
    stats = {}
    for s in game.seats:
        stats[s.player_id] = {
            "name": s.player.display_name, "score": s.score,
            "plays": 0, "points": 0, "bingos": 0,
            "passes": 0, "exchanges": 0, "best": None,
        }
    for m in game.moves.all():
        d = stats.get(m.player_id)
        if d is None:
            continue
        if m.kind == Move.PLAY:
            d["plays"] += 1
            d["points"] += m.points
            if len(m.placements or []) == RACK_SIZE:
                d["bingos"] += 1
            word = m.words[0][0] if m.words else ""
            if d["best"] is None or m.points > d["best"][1]:
                d["best"] = (word, m.points)
        elif m.kind == Move.PASS:
            d["passes"] += 1
        elif m.kind == Move.EXCHANGE:
            d["exchanges"] += 1
    for d in stats.values():
        d["avg"] = round(d["points"] / d["plays"], 1) if d["plays"] else 0
    return list(stats.values())
