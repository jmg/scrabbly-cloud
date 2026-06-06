from django.test import TestCase

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
