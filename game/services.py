"""Game orchestration: ties the engine, models and ratings together.

All mutating operations run inside a transaction and return the updated Game.
Turn/seat enforcement lives here so both HTTP views and the WebSocket consumer
share one source of truth.
"""

from django.conf import settings
from django.db import transaction

from accounts.models import User

from . import ratings
from .engine import (
    BLANK,
    RACK_SIZE,
    Bag,
    Board,
    InvalidMove,
    Placement,
    WordList,
    score_letter,
    validate_and_score,
)
from .models import Game, GamePlayer, Move

_wordlist = None


def get_wordlist():
    global _wordlist
    if _wordlist is None:
        path = getattr(settings, "SCRABBLE_DICTIONARY_PATH", "")
        _wordlist = WordList.from_file(path) if path else WordList()
    return _wordlist


def _draw_for(game, seat, bag):
    need = RACK_SIZE - len(seat.rack)
    if need > 0:
        seat.rack = list(seat.rack) + bag.draw(need)


def create_game(user, rated=True, max_players=2):
    with transaction.atomic():
        bag = Bag()
        game = Game.objects.create(
            status=Game.WAITING, rated=rated, max_players=max_players,
            board=Board().serialize(), bag=bag.letters,
        )
        seat = GamePlayer.objects.create(game=game, player=user, seat=0)
        _draw_for(game, seat, bag)
        seat.save()
        game.bag = bag.letters
        game.save(update_fields=["bag"])
    return game


def join_game(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        existing = game.seat_for(user)
        if existing:
            return game
        if game.status != Game.WAITING or game.is_full:
            raise InvalidMove("La partida ya no admite jugadores.")
        bag = Bag(letters=list(game.bag))
        seat = GamePlayer.objects.create(
            game=game, player=user, seat=game.players.count()
        )
        _draw_for(game, seat, bag)
        seat.save()
        game.bag = bag.letters
        if game.is_full:
            game.status = Game.ACTIVE
        game.save()
    return game


def quick_pair(user, rated=True):
    """Join the oldest waiting game with a free seat, or open a new one."""
    with transaction.atomic():
        candidate = (
            Game.objects.select_for_update(skip_locked=True)
            .filter(status=Game.WAITING, rated=rated)
            .exclude(players__player=user)
            .order_by("created_at")
            .first()
        )
    if candidate:
        return join_game(candidate, user)
    return create_game(user, rated=rated)


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


def make_play(game, user, placements_data):
    """placements_data: list of {letter, row, col, is_blank}."""
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = _require_turn(game, user)

        placements = [
            Placement(
                letter=str(d["letter"]).upper(),
                row=int(d["row"]), col=int(d["col"]),
                is_blank=bool(d.get("is_blank")),
            )
            for d in placements_data
        ]
        board = Board.deserialize(game.board)
        result = validate_and_score(board, placements, get_wordlist())

        seat.rack = _consume_from_rack(seat.rack, placements)
        board.apply(placements)
        bag = Bag(letters=list(game.bag))
        _draw_for(game, seat, bag)

        seat.score += result.points
        seat.save()

        game.board = board.serialize()
        game.bag = bag.letters
        game.consecutive_passes = 0
        _record_move(game, user, Move.PLAY, placements_data, result.words, result.points)

        went_out = len(seat.rack) == 0 and len(bag) == 0
        if went_out:
            _finish(game, last_seat=seat)
        else:
            _advance_turn(game)
            game.save()
    return game


def make_pass(game, user):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        _require_turn(game, user)
        game.consecutive_passes += 1
        _record_move(game, user, Move.PASS, [], [], 0)
        # End if everyone passed twice in a row.
        if game.consecutive_passes >= 2 * game.players.count():
            _finish(game)
        else:
            _advance_turn(game)
            game.save()
    return game


def make_exchange(game, user, letters):
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        seat = _require_turn(game, user)
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
        seat.save()
        game.bag = bag.letters
        game.consecutive_passes = 0
        _record_move(game, user, Move.EXCHANGE, [], [], 0)
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


def _rack_value(rack):
    return sum(score_letter(letter, letter == BLANK) for letter in rack)


def _finish(game, last_seat=None, loser=None):
    """Apply end-of-game scoring and rating changes, then mark finished."""
    seats = list(game.players.all())

    # Endgame tile adjustment: each player loses their remaining rack value; if
    # someone emptied their rack, they also gain the sum of everyone else's.
    leftover_total = 0
    for seat in seats:
        value = _rack_value(seat.rack)
        seat.score -= value
        leftover_total += value
    if last_seat is not None:
        last_seat.score += leftover_total

    # Determine winner. A resigning player is forced last.
    ranked = sorted(
        seats,
        key=lambda s: (-1 if s is loser else 0, s.score),
        reverse=True,
    )
    top_score = ranked[0].score
    winners = [s for s in ranked if s.score == top_score and s is not loser]
    is_draw = len(winners) > 1
    game.winner = None if is_draw else winners[0].player

    _apply_ratings(game, seats, loser)

    for seat in seats:
        seat.save()
    for seat in seats:
        _update_stats(seat)

    game.status = Game.FINISHED
    game.save()


def _apply_ratings(game, seats, loser):
    if not game.rated:
        for seat in seats:
            if seat.result == "":
                _set_result(seat, loser)
        return
    standings = [
        {"rating": seat.player.rating,
         "points": -1 if seat is loser else seat.score}
        for seat in seats
    ]
    new_ratings = ratings.compute_updates(standings)
    for seat, new_rating in zip(seats, new_ratings):
        seat.rating_before = seat.player.rating
        seat.rating_after = new_rating
        seat.player.rating = new_rating
        seat.player.save(update_fields=["rating"])
        _set_result(seat, loser)


def _set_result(seat, loser):
    game = seat.game
    if seat is loser:
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
    return {
        "id": game.pk,
        "status": game.status,
        "rated": game.rated,
        "turn_user_id": current.player_id if current and game.status == Game.ACTIVE else None,
        "bag_count": len(game.bag),
        "winner_id": game.winner_id,
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
                "seat": s.seat,
                "score": s.score,
                "tiles_left": len(s.rack),
                "result": s.result,
                "rating_delta": s.rating_delta,
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
            }
            for m in game.moves.select_related("player")
        ],
    }


def rack_for(game, user):
    seat = game.seat_for(user)
    return list(seat.rack) if seat else []
