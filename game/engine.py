"""Pure-Python Scrabble engine.

Self-contained replacement for the old external ``scrabbly`` dependency.
Implements a standard 15x15 board, the modern Spanish tile distribution
(post-2008, no CH/LL/RR digraphs), premium squares, scoring (including the
50-point bingo bonus) and move validation. Word-list validation is optional
and pluggable so the game stays playable without a bundled dictionary.

The engine is intentionally state-light: it operates on plain data
structures so it can be driven from Django models or from tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

BOARD_SIZE = 15
CENTER = (7, 7)
RACK_SIZE = 7
BINGO_BONUS = 50
BLANK = "?"

# Modern Spanish distribution without digraphs (100 tiles). The 3 historical
# digraph tiles (CH, LL, RR) are folded into C, L and R. (count, points)
TILE_DISTRIBUTION = {
    "A": (12, 1), "B": (2, 3), "C": (5, 3), "D": (5, 2), "E": (12, 1),
    "F": (1, 4), "G": (2, 2), "H": (2, 4), "I": (6, 1), "J": (1, 8),
    "L": (5, 1), "M": (2, 3), "N": (5, 1), "Ñ": (1, 8), "O": (9, 1),
    "P": (2, 3), "Q": (1, 5), "R": (6, 1), "S": (6, 1), "T": (4, 1),
    "U": (5, 1), "V": (1, 4), "X": (1, 8), "Y": (1, 4), "Z": (1, 10),
    BLANK: (2, 0),
}

LETTER_POINTS = {letter: points for letter, (count, points) in TILE_DISTRIBUTION.items()}

# Premium squares. "TW"=triple word, "DW"=double word, "TL"=triple letter,
# "DL"=double letter. Defined for one quadrant + axes and mirrored to fill the
# board symmetrically.
_PREMIUM_SEED = {
    "TW": [(0, 0), (0, 7), (7, 0)],
    "DW": [(1, 1), (2, 2), (3, 3), (4, 4)],
    "TL": [(1, 5), (5, 1), (5, 5)],
    "DL": [(0, 3), (3, 0), (2, 6), (6, 2), (6, 6), (3, 7), (7, 3)],
}


def _build_premiums():
    premiums = {}
    for kind, cells in _PREMIUM_SEED.items():
        for r, c in cells:
            for rr, cc in {
                (r, c), (r, BOARD_SIZE - 1 - c),
                (BOARD_SIZE - 1 - r, c), (BOARD_SIZE - 1 - r, BOARD_SIZE - 1 - c),
            }:
                premiums[(rr, cc)] = kind
    premiums[CENTER] = "DW"  # star square counts as double word
    return premiums


PREMIUMS = _build_premiums()


@dataclass
class Placement:
    """A single tile placed during a move."""

    letter: str            # the scoring letter (resolved blank value)
    row: int
    col: int
    is_blank: bool = False  # True if it came from a blank tile (0 points)


class InvalidMove(Exception):
    """Raised when a submitted move breaks the rules."""


class Bag:
    """The tile bag. Stores letters as a shuffled list."""

    def __init__(self, letters=None, rng=None):
        self.rng = rng or random.Random()
        if letters is None:
            letters = []
            for letter, (count, _points) in TILE_DISTRIBUTION.items():
                letters.extend([letter] * count)
            self.rng.shuffle(letters)
        self.letters = list(letters)

    def __len__(self):
        return len(self.letters)

    def draw(self, n):
        drawn = self.letters[:n]
        self.letters = self.letters[n:]
        return drawn

    def put_back(self, letters):
        self.letters.extend(letters)
        self.rng.shuffle(self.letters)


class Board:
    """15x15 grid of placed letters plus blank bookkeeping."""

    def __init__(self, grid=None, blanks=None):
        # grid[(r, c)] -> letter ; blanks is a set of (r, c) placed from blanks
        self.grid = dict(grid or {})
        self.blanks = set(tuple(b) for b in (blanks or []))

    def is_empty(self):
        return not self.grid

    def letter_at(self, row, col):
        return self.grid.get((row, col))

    def apply(self, placements):
        for p in placements:
            self.grid[(p.row, p.col)] = p.letter
            if p.is_blank:
                self.blanks.add((p.row, p.col))

    def serialize(self):
        return {
            "grid": {f"{r},{c}": letter for (r, c), letter in self.grid.items()},
            "blanks": [list(b) for b in self.blanks],
        }

    @classmethod
    def deserialize(cls, data):
        if not data:
            return cls()
        grid = {}
        for key, letter in (data.get("grid") or {}).items():
            r, c = key.split(",")
            grid[(int(r), int(c))] = letter
        return cls(grid=grid, blanks=data.get("blanks"))


@dataclass
class MoveResult:
    points: int
    words: list = field(default_factory=list)  # list of (word, points)


def score_letter(letter, is_blank):
    return 0 if is_blank else LETTER_POINTS.get(letter, 0)


class WordList:
    """Optional dictionary. Empty list -> validation disabled (anything goes)."""

    def __init__(self, words=None):
        self.words = set(w.strip().upper() for w in words) if words else None

    @property
    def enabled(self):
        return self.words is not None

    def is_valid(self, word):
        if not self.enabled:
            return True
        return word.upper() in self.words

    @classmethod
    def from_file(cls, path):
        try:
            with open(path, encoding="utf-8") as fh:
                return cls(fh.read().splitlines())
        except OSError:
            return cls()


def _in_bounds(r, c):
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE


def validate_and_score(board: Board, placements, wordlist: WordList | None = None):
    """Validate a move against the board and return its MoveResult.

    Raises ``InvalidMove`` on any rule violation. Does not mutate the board.
    """
    wordlist = wordlist or WordList()
    if not placements:
        raise InvalidMove("No colocaste ninguna ficha.")

    coords = [(p.row, p.col) for p in placements]
    if len(set(coords)) != len(coords):
        raise InvalidMove("Dos fichas en la misma casilla.")
    for r, c in coords:
        if not _in_bounds(r, c):
            raise InvalidMove("Ficha fuera del tablero.")
        if board.letter_at(r, c) is not None:
            raise InvalidMove("Casilla ocupada.")

    rows = {r for r, _ in coords}
    cols = {c for _, c in coords}
    if len(rows) != 1 and len(cols) != 1:
        raise InvalidMove("Las fichas deben estar en una sola fila o columna.")
    horizontal = len(rows) == 1

    # Build a temporary view of the board including the new placements.
    temp = dict(board.grid)
    blank_cells = set(board.blanks)
    for p in placements:
        temp[(p.row, p.col)] = p.letter
        if p.is_blank:
            blank_cells.add((p.row, p.col))

    # Contiguity: the placed run plus any bridged existing tiles must be solid.
    line = sorted(coords, key=lambda x: (x[1] if horizontal else x[0]))
    fixed = line[0][0] if horizontal else line[0][1]
    lo = line[0][1] if horizontal else line[0][0]
    hi = line[-1][1] if horizontal else line[-1][0]
    for i in range(lo, hi + 1):
        cell = (fixed, i) if horizontal else (i, fixed)
        if cell not in temp:
            raise InvalidMove("Las fichas deben formar una palabra contigua.")

    # Connection rule: first move covers center; otherwise must touch a tile.
    if board.is_empty():
        if CENTER not in coords:
            raise InvalidMove("La primera palabra debe pasar por el centro.")
    else:
        touches = False
        for r, c in coords:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if board.letter_at(r + dr, c + dc) is not None:
                    touches = True
        if not touches:
            raise InvalidMove("La palabra debe conectarse con fichas existentes.")

    placed_set = set(coords)

    def collect_word(start_r, start_c, dr, dc):
        """Walk back to the start of a word then forward, scoring it."""
        r, c = start_r, start_c
        while _in_bounds(r - dr, c - dc) and (r - dr, c - dc) in temp:
            r -= dr
            c -= dc
        letters = []
        word_mult = 1
        score = 0
        n_cells = 0
        while _in_bounds(r, c) and (r, c) in temp:
            letter = temp[(r, c)]
            is_blank = (r, c) in blank_cells
            base = score_letter(letter, is_blank)
            if (r, c) in placed_set:  # premiums only apply to freshly placed tiles
                premium = PREMIUMS.get((r, c))
                if premium == "DL":
                    base *= 2
                elif premium == "TL":
                    base *= 3
                elif premium == "DW":
                    word_mult *= 2
                elif premium == "TW":
                    word_mult *= 3
            score += base
            letters.append(letter)
            n_cells += 1
            r += dr
            c += dc
        return "".join(letters), score * word_mult, n_cells

    words = []
    total = 0

    # Main word (along the line of play).
    if horizontal:
        word, pts, n = collect_word(fixed, lo, 0, 1)
    else:
        word, pts, n = collect_word(lo, fixed, 1, 0)
    if n > 1:
        words.append((word, pts))
        total += pts

    # Cross words formed by each newly placed tile.
    for p in placements:
        if horizontal:
            word, pts, n = collect_word(p.row, p.col, 1, 0)
        else:
            word, pts, n = collect_word(p.row, p.col, 0, 1)
        if n > 1:
            words.append((word, pts))
            total += pts

    if not words:
        raise InvalidMove("La jugada no forma ninguna palabra.")

    for word, _pts in words:
        if not wordlist.is_valid(word):
            raise InvalidMove(f"«{word}» no es una palabra válida.")

    if len(placements) == RACK_SIZE:
        total += BINGO_BONUS

    return MoveResult(points=total, words=words)
