"""A strong Scrabble move-generating AI opponent.

Uses a minimised DAWG (directed acyclic word graph) built from the language
word list plus the classic anchor/cross-check generation: it finds *every*
legal play on the board — hooks, extensions, through-plays and parallel plays —
prunes them with per-square cross-checks, scores each with the engine and
selects one according to a difficulty level.

Five levels span beginner to expert; the expert level ranks by equity
(score + a rack-leave heuristic) rather than raw score.
"""

import random
import time
from collections import Counter

from .engine import (
    BLANK,
    BOARD_SIZE,
    CENTER,
    Placement,
    InvalidMove,
    validate_and_score,
)

LEVELS = ("beginner", "easy", "medium", "hard", "expert")
TIME_BUDGET = 2.5  # seconds per move (safety net; usually far faster)
MAX_CANDIDATES = 9000


# --------------------------------------------------------------------------- #
# DAWG
# --------------------------------------------------------------------------- #
class _Node:
    __slots__ = ("final", "edges", "id")
    _counter = 0

    def __init__(self):
        self.final = False
        self.edges = {}
        self.id = _Node._counter
        _Node._counter += 1


class Dawg:
    """Minimised DAWG built incrementally from sorted words (Daciuk)."""

    def __init__(self, words):
        self.root = _Node()
        self._prev = ""
        self._unchecked = []
        self._minimized = {}
        for w in sorted(words):
            self._insert(w)
        self._minimize(0)
        self._unchecked = None
        self._minimized = None

    def _insert(self, word):
        cp = 0
        for a, b in zip(word, self._prev):
            if a != b:
                break
            cp += 1
        self._minimize(cp)
        node = self.root if not self._unchecked else self._unchecked[-1][2]
        for ch in word[cp:]:
            nxt = _Node()
            node.edges[ch] = nxt
            self._unchecked.append((node, ch, nxt))
            node = nxt
        node.final = True
        self._prev = word

    def _sig(self, node):
        return (node.final, tuple((c, ch.id) for c, ch in sorted(node.edges.items())))

    def _minimize(self, down_to):
        for i in range(len(self._unchecked) - 1, down_to - 1, -1):
            parent, ch, child = self._unchecked[i]
            sig = self._sig(child)
            if sig in self._minimized:
                parent.edges[ch] = self._minimized[sig]
            else:
                self._minimized[sig] = child
            self._unchecked.pop()

    def contains(self, letters):
        node = self.root
        for ch in letters:
            node = node.edges.get(ch)
            if node is None:
                return False
        return node.final


_dawg_cache = {}


def get_dawg(language, wordlist):
    if language not in _dawg_cache:
        _dawg_cache[language] = Dawg(wordlist.words or ())
    return _dawg_cache[language]


# --------------------------------------------------------------------------- #
# Rack-leave heuristic (used by the expert level)
# --------------------------------------------------------------------------- #
_LEAVE = {
    BLANK: 25, "S": 8, "E": 4, "A": 3, "R": 3, "I": 2, "N": 2, "L": 2,
    "O": 1, "T": 1, "D": 1, "C": 1, "M": 0, "P": 0, "U": -1, "B": -1,
    "G": -2, "H": -3, "F": -3, "V": -3, "Y": -3, "K": -3, "J": -4,
    "X": -4, "W": -4, "Z": -5, "Ñ": -5, "Q": -6,
}


def _leave_value(letters):
    c = Counter(letters)
    v = 0
    for letter, count in c.items():
        v += _LEAVE.get(letter, 0)
        if count > 1:
            v -= 2 * (count - 1)  # duplicates are awkward to use
    if c.get("Q", 0) and not c.get("U", 0):
        v -= 5
    return v


# --------------------------------------------------------------------------- #
# Move generation
# --------------------------------------------------------------------------- #
def _ib(r, c):
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE


def _at(board, orient, line, pos):
    return board.letter_at(line, pos) if orient == "H" else board.letter_at(pos, line)


def _coord(orient, line, pos):
    return (line, pos) if orient == "H" else (pos, line)


def _cross_sets(board, orient, dawg, alphabet):
    """Allowed letters for each empty square so the cross word stays valid.

    A missing entry means 'no cross word here' (any letter, no connection);
    a present set means the square has neighbours (so playing connects).
    """
    dr, dc = (1, 0) if orient == "H" else (0, 1)
    out = {}
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board.letter_at(r, c) is not None:
                continue
            pre = []
            ar, ac = r - dr, c - dc
            while _ib(ar, ac) and board.letter_at(ar, ac):
                pre.append(board.letter_at(ar, ac))
                ar -= dr
                ac -= dc
            pre.reverse()
            suf = []
            br, bc = r + dr, c + dc
            while _ib(br, bc) and board.letter_at(br, bc):
                suf.append(board.letter_at(br, bc))
                br += dr
                bc += dc
            if not pre and not suf:
                continue
            out[(r, c)] = {L for L in alphabet if dawg.contains(pre + [L] + suf)}
    return out


def generate(board, rack, ruleset, wordlist, language, time_budget=TIME_BUDGET):
    """Return {key: (points, placements_data, max_word_len, leave)} for all plays."""
    if not wordlist.enabled:
        return {}
    dawg = get_dawg(language, wordlist)
    alphabet = [l for l in ruleset.points if l != BLANK]
    empty = board.is_empty()
    rack_counter = Counter(rack)
    deadline = time.monotonic() + time_budget
    moves = {}
    seen = set()

    def record(placed, connects):
        if not (placed and connects):
            return
        key = frozenset(placed)
        if key in seen:
            return
        seen.add(key)
        coords = {(r, c) for r, c, _, _ in placed}
        if empty and CENTER not in coords:
            return
        placements = [Placement(L, r, c, b) for (r, c, L, b) in placed]
        try:
            res = validate_and_score(board, placements, wordlist, ruleset)
        except InvalidMove:
            return
        used = Counter(BLANK if b else L for (_, _, L, b) in placed)
        leave = list((rack_counter - used).elements())
        max_word = max((len(w) for w, _ in res.words), default=0)
        data = [{"letter": L, "row": r, "col": c, "is_blank": b} for (r, c, L, b) in placed]
        moves[key] = (res.points, data, max_word, leave)

    def extend(orient, line, pos, node, placed, connects, rack, cross):
        if pos >= BOARD_SIZE:
            if node.final:
                record(placed, connects)
            return
        existing = _at(board, orient, line, pos)
        if existing is not None:
            child = node.edges.get(existing)
            if child is not None:
                extend(orient, line, pos + 1, child, placed, True, rack, cross)
            return
        if node.final:
            record(placed, connects)
        r, c = _coord(orient, line, pos)
        allowed = cross.get((r, c))  # None => any letter, no connection
        for L, child in node.edges.items():
            if allowed is not None and L not in allowed:
                continue
            if rack.get(L, 0) > 0:
                tile, is_blank = L, False
            elif rack.get(BLANK, 0) > 0:
                tile, is_blank = BLANK, True
            else:
                continue
            rack[tile] -= 1
            placed.append((r, c, L, is_blank))
            extend(orient, line, pos + 1, child, placed,
                   connects or allowed is not None, rack, cross)
            placed.pop()
            rack[tile] += 1

    for orient in ("H", "V"):
        cross = _cross_sets(board, orient, dawg, alphabet)
        for line in range(BOARD_SIZE):
            if empty and line != CENTER[0]:
                continue
            for start in range(BOARD_SIZE):
                if start > 0 and _at(board, orient, line, start - 1) is not None:
                    continue
                extend(orient, line, start, dawg.root, [], empty,
                       rack_counter.copy(), cross)
            if len(moves) > MAX_CANDIDATES or time.monotonic() > deadline:
                return moves
    return moves


def best_moves(board, rack, ruleset, wordlist, language, **kw):
    """Backward-compatible: list of (points, placements_data), best first."""
    moves = generate(board, rack, ruleset, wordlist, language, **kw)
    out = [(p, data) for (p, data, _ml, _lv) in moves.values()]
    out.sort(key=lambda m: m[0], reverse=True)
    return out


def choose_move(board, rack, ruleset, wordlist, language, difficulty="medium"):
    """Pick a move for the given level. Returns placements_data or None."""
    moves = list(generate(board, rack, ruleset, wordlist, language).values())
    if not moves:
        return None
    moves.sort(key=lambda m: m[0])  # ascending by points
    n = len(moves)

    if difficulty == "beginner":
        pool = [m for m in moves if m[2] <= 4] or moves
        return random.choice(pool[:max(1, len(pool) // 2)])[1]
    if difficulty == "easy":
        pool = [m for m in moves if m[2] <= 6] or moves
        return random.choice(pool[:max(1, len(pool) * 2 // 3)])[1]
    if difficulty == "medium":
        band = moves[int(n * 0.55):int(n * 0.85)] or moves[-1:]
        return random.choice(band)[1]
    if difficulty == "expert":
        return max(moves, key=lambda m: m[0] + _leave_value(m[3]))[1]
    return moves[-1][1]  # hard: highest score
