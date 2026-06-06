"""Read-only public JSON API.

Lightweight endpoints built on plain JsonResponse (no DRF dependency) so other
clients and bots can read the lobby, games, leaderboard and player stats.
"""

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from . import services
from .models import Game

User = get_user_model()


def _game_summary(game):
    return {
        "id": game.pk,
        "status": game.status,
        "language": game.language,
        "rated": game.rated,
        "clock": game.clock_label,
        "url": f"/game/{game.pk}/",
        "players": [
            {"name": s.player.display_name, "rating": s.player.rating, "score": s.score}
            for s in game.seats
        ],
    }


def games(request):
    """List joinable and in-progress games (optionally filter by ?status=)."""
    status = request.GET.get("status")
    statuses = [status] if status in (Game.WAITING, Game.ACTIVE) else [Game.WAITING, Game.ACTIVE]
    qs = (
        Game.objects.filter(status__in=statuses)
        .prefetch_related("players__player")
        .order_by("-created_at")[:100]
    )
    return JsonResponse({"games": [_game_summary(g) for g in qs]})


def game(request, game_id):
    g = get_object_or_404(Game, pk=game_id)
    return JsonResponse(services.public_state(g))


def leaderboard(request):
    top = User.objects.filter(is_guest=False, is_bot=False).order_by("-rating")[:50]
    return JsonResponse({"players": [
        {"username": u.username, "rating": u.rating,
         "games_played": u.games_played, "wins": u.wins}
        for u in top
    ]})


def player(request, username):
    u = get_object_or_404(User, username=username, is_guest=False)
    return JsonResponse({
        "username": u.username,
        "rating": u.rating,
        "games_played": u.games_played,
        "wins": u.wins,
        "losses": u.losses,
        "draws": u.draws,
    })
