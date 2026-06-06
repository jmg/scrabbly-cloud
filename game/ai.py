"""A Scrabble move-generating AI opponent.

Generates all legal single-line plays (hooks, extensions and through-plays that
include at least one existing tile, plus first-move plays through the centre),
scores them with the engine and picks one according to difficulty. It does not
attempt parallel plays, so it is a solid practice opponent rather than a
world-class engine. A time budget keeps every move responsive.
"""

import random
import time
from collections import Counter

from .engine import (
    BLANK,
    BOARD_SIZE,
    CENTER,
    RACK_SIZE,
    Board,
    InvalidMove,
    Placement,
    validate_and_score,
)

_by_len_cache = {}
TIME_BUDGET = 1.2  # seconds per move


def _words_by_len(language, wordlist):
    if language not in _by_len_cache:
        groups = {}
        for w in (wordlist.words or ()):
            groups.setdefault(len(w), []).append(w)
        _by_len_cache[language] = groups
    return _by_len_cache[language]


def _assign(letters, counts, blanks):
    """Decide which tiles come from the rack vs. blanks. Returns flags or None."""
    c = counts.copy()
    b = blanks
    flags = []
    for ch in letters:
        if c.get(ch, 0) > 0:
            c[ch] -= 1
            flags.append(False)
        elif b > 0:
            b -= 1
            flags.append(True)
        else:
            return None
    return flags


def _line_cells(board, orient, index):
    """Return the 15 letters (or None) along a row or column."""
    if orient == "H":
        return [board.letter_at(index, c) for c in range(BOARD_SIZE)]
    return [board.letter_at(r, index) for r in range(BOARD_SIZE)]


def _coord(orient, index, pos):
    return (index, pos) if orient == "H" else (pos, index)


def _runs(line):
    """Yield (start, end) spans that, once filled, form a self-contained word."""
    n = len(line)
    out = []
    for s in range(n):
        if s > 0 and line[s - 1] is not None:
            continue
        for e in range(s + 1, n):
            if e + 1 < n and line[e + 1] is not None:
                continue
            seg = line[s:e + 1]
            if any(x is not None for x in seg) and any(x is None for x in seg):
                out.append((s, e))
    return out


def best_moves(board, rack, ruleset, wordlist, language, time_budget=TIME_BUDGET):
    """Return scored legal plays: list of (points, placements_data)."""
    by_len = _words_by_len(language, wordlist)
    counts = Counter(rack)
    blanks = counts.pop(BLANK, 0)
    results = []
    deadline = time.monotonic() + time_budget

    def consider(placements_rel, coords):
        placements = [
            Placement(letter=ch, row=r, col=c, is_blank=flag)
            for (ch, flag), (r, c) in zip(placements_rel, coords)
        ]
        try:
            res = validate_and_score(board, placements, wordlist, ruleset)
        except InvalidMove:
            return
        data = [
            {"letter": p.letter, "row": p.row, "col": p.col, "is_blank": p.is_blank}
            for p in placements
        ]
        results.append((res.points, data))

    tiles_available = len(rack)

    if board.is_empty():
        max_len = min(tiles_available, max(by_len) if by_len else 0)
        for length in range(2, max_len + 1):
            for w in by_len.get(length, ()):
                flags = _assign(list(w), counts, blanks)
                if flags is None:
                    continue
                for start in range(CENTER[1] - length + 1, CENTER[1] + 1):
                    if start < 0 or start + length > BOARD_SIZE:
                        continue
                    coords = [(CENTER[0], start + i) for i in range(length)]
                    consider(list(zip(w, flags)), coords)
                if time.monotonic() > deadline:
                    return results
        return results

    # Collect candidate spans, then process the cheapest (fewest tiles to place)
    # first so productive short plays are found before the time budget runs out.
    spans = []
    for orient in ("H", "V"):
        for index in range(BOARD_SIZE):
            line = _line_cells(board, orient, index)
            for s, e in _runs(line):
                empties = [i - s for i in range(s, e + 1) if line[i] is None]
                if not empties or len(empties) > tiles_available:
                    continue
                fixed = {i - s: line[i] for i in range(s, e + 1) if line[i] is not None}
                spans.append((len(empties), orient, index, s, e, fixed, empties))
    spans.sort(key=lambda sp: sp[0])

    for _, orient, index, s, e, fixed, empties in spans:
        length = e - s + 1
        checked = 0
        for w in by_len.get(length, ()):
            checked += 1
            if checked % 4000 == 0 and time.monotonic() > deadline:
                return results
            if any(w[k] != ch for k, ch in fixed.items()):
                continue
            flags = _assign([w[k] for k in empties], counts, blanks)
            if flags is None:
                continue
            placements_rel = [(w[k], flags[i]) for i, k in enumerate(empties)]
            coords = [_coord(orient, index, s + k) for k in empties]
            consider(placements_rel, coords)
        if time.monotonic() > deadline:
            return results
    return results


def choose_move(board, rack, ruleset, wordlist, language, difficulty="medium"):
    """Pick a move by difficulty. Returns placements_data or None (no move)."""
    moves = best_moves(board, rack, ruleset, wordlist, language)
    if not moves:
        return None
    moves.sort(key=lambda m: m[0], reverse=True)
    if difficulty == "hard":
        chosen = moves[0]
    elif difficulty == "easy":
        chosen = random.choice(moves[len(moves) // 2:] or moves)
    else:  # medium
        chosen = random.choice(moves[:max(1, len(moves) // 3)])
    return chosen[1]
