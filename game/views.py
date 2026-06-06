import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .engine import InvalidMove
from .models import Game
from .realtime import notify_update

User = get_user_model()


def lobby(request):
    waiting = (
        Game.objects.filter(status=Game.WAITING)
        .exclude(players__player=request.user)
        .prefetch_related("players__player")
    )
    active = (
        Game.objects.filter(status=Game.ACTIVE)
        .prefetch_related("players__player")[:30]
    )
    mine = (
        Game.objects.filter(players__player=request.user)
        .exclude(status=Game.FINISHED)
        .exclude(status=Game.ABORTED)
        .prefetch_related("players__player")
        .distinct()
    )
    leaders = User.objects.filter(is_guest=False).order_by("-rating")[:10]
    return render(request, "game/lobby.html", {
        "waiting": waiting, "active": active, "mine": mine, "leaders": leaders,
    })


@require_POST
def create_game(request):
    rated = request.POST.get("rated", "1") == "1"
    game = services.create_game(request.user, rated=rated)
    return redirect("game_detail", game_id=game.pk)


@require_POST
def quick_pair(request):
    game = services.quick_pair(request.user)
    notify_update(game.pk)
    return redirect("game_detail", game_id=game.pk)


@require_POST
def join_game(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.join_game(game, request.user)
    except InvalidMove as exc:
        return _error(request, str(exc))
    notify_update(game.pk)
    return redirect("game_detail", game_id=game.pk)


def game_detail(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    seat = game.seat_for(request.user)
    state = services.public_state(game)
    rack = services.rack_for(game, request.user)
    return render(request, "game/game.html", {
        "game": game,
        "is_player": seat is not None,
        "state_json": json.dumps(state),
        "rack_json": json.dumps(rack),
        "me_id": request.user.pk,
    })


def game_state(request, game_id):
    """JSON bootstrap / polling fallback. Includes the caller's own rack."""
    game = get_object_or_404(Game, pk=game_id)
    return JsonResponse({
        "state": services.public_state(game),
        "rack": services.rack_for(game, request.user),
    })


@require_POST
def play(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        placements = json.loads(request.body or "{}").get("placements", [])
        game = services.make_play(game, request.user, placements)
    except (InvalidMove, ValueError, KeyError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
def passturn(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.make_pass(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
def exchange(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        letters = json.loads(request.body or "{}").get("letters", [])
        game = services.make_exchange(game, request.user, letters)
    except (InvalidMove, ValueError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
def resign(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.resign(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


def _error(request, message):
    return render(request, "game/error.html", {"message": message}, status=400)
