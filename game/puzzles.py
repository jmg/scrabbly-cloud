"""Puzzle generation and evaluation.

A puzzle is a board position plus a rack; the goal is to find the highest
scoring legal move. Positions are produced by short AI self-play, and the
target move is the engine's top-scoring play, so puzzles are always solvable.
"""

import datetime
import random
from collections import Counter

from django.db import IntegrityError

from . import ai
from .engine import BLANK, Board, InvalidMove, Placement, get_ruleset, validate_and_score
from .models import Puzzle
from .services import get_wordlist


def _selfplay(board, racks, bag, ruleset, wl, language, n_moves):
    turn = 0
    played = 0
    while played < n_moves:
        rk = racks[turn % 2]
        mv = ai.choose_move(board, rk, ruleset, wl, language, "medium")
        if not mv:
            break
        placements = [Placement(p["letter"], p["row"], p["col"], p["is_blank"]) for p in mv]
        try:
            validate_and_score(board, placements, wl, ruleset)
        except InvalidMove:
            break
        board.apply(placements)
        for p in mv:
            tile = BLANK if p["is_blank"] else p["letter"]
            if tile in rk:
                rk.remove(tile)
        rk += bag.draw(len(mv))
        played += 1
        turn += 1
    return turn


def generate_puzzle(language="es", rng=None, min_score=18, attempts=14):
    rng = rng or random.Random()
    ruleset = get_ruleset(language)
    wl = get_wordlist(language)
    if not wl.enabled:
        return None
    for _ in range(attempts):
        bag = ruleset.new_bag(rng=rng)
        board = Board()
        racks = [bag.draw(7), bag.draw(7)]
        turn = _selfplay(board, racks, bag, ruleset, wl, language, rng.randint(2, 6))
        rk = racks[turn % 2]
        moves = ai.best_moves(board, rk, ruleset, wl, language)
        if len(moves) >= 6 and moves[0][0] >= min_score:
            best_score, best_data = moves[0]
            placements = [Placement(p["letter"], p["row"], p["col"], p["is_blank"])
                          for p in best_data]
            res = validate_and_score(board, placements, wl, ruleset)
            word = max((w for w, _ in res.words), key=len) if res.words else ""
            return Puzzle(
                language=language, board=board.serialize(), rack=rk,
                best_move=best_data, best_score=best_score, best_word=word,
            )
    return None


def new_training_puzzle(language="es"):
    p = generate_puzzle(language)
    if p:
        p.save()
    return p


def get_daily(language="es"):
    today = datetime.date.today()
    existing = Puzzle.objects.filter(date=today, language=language).first()
    if existing:
        return existing
    # Seed by date so the daily is stable if generated more than once.
    p = generate_puzzle(language, rng=random.Random(int(today.strftime("%Y%m%d"))))
    if p is None:
        return None
    p.date = today
    try:
        p.save()
    except IntegrityError:
        return Puzzle.objects.get(date=today, language=language)
    return p


def evaluate(puzzle, placements_data):
    """Score the user's move; raises InvalidMove if illegal or off-rack."""
    ruleset = get_ruleset(puzzle.language)
    wl = get_wordlist(puzzle.language)
    board = Board.deserialize(puzzle.board)

    available = Counter(puzzle.rack)
    placements = []
    for p in placements_data:
        is_blank = bool(p.get("is_blank"))
        tile = BLANK if is_blank else p["letter"]
        if available[tile] <= 0:
            raise InvalidMove("Usaste una ficha que no está en tu atril.")
        available[tile] -= 1
        placements.append(Placement(p["letter"], int(p["row"]), int(p["col"]), is_blank))

    res = validate_and_score(board, placements, wl, ruleset)
    return res.points
