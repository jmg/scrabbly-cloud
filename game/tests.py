from django.test import TestCase

from .engine import (
    Bag,
    Board,
    InvalidMove,
    Placement,
    WordList,
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
