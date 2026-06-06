"""ELO rating updates.

A standard ELO implementation good enough for a Lichess-style ladder. For
N-player games we apply pairwise ELO between every pair of seats and sum the
deltas, which generalises the 2-player formula sensibly.
"""

K_FACTOR = 32


def expected(rating_a, rating_b):
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def pairwise_delta(rating_a, rating_b, score_a):
    """Return the rating change for player A. ``score_a`` is 1/0.5/0."""
    return round(K_FACTOR * (score_a - expected(rating_a, rating_b)))


def outcome_score(my_points, their_points):
    if my_points > their_points:
        return 1.0
    if my_points < their_points:
        return 0.0
    return 0.5


def compute_updates(standings):
    """Compute new ratings for a finished game.

    ``standings`` is a list of dicts: {"rating": int, "points": int}.
    Returns a list of new ratings aligned to the input order.
    """
    n = len(standings)
    deltas = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            score = outcome_score(standings[i]["points"], standings[j]["points"])
            deltas[i] += pairwise_delta(
                standings[i]["rating"], standings[j]["rating"], score
            )
    # Average the accumulated delta so a 2-player game keeps the classic
    # +/-K swing rather than scaling with opponent count.
    divisor = max(n - 1, 1)
    return [
        standings[i]["rating"] + round(deltas[i] / divisor) for i in range(n)
    ]
