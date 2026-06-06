import json

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .engine import InvalidMove
from .models import Game
from .ratelimit import rate_limit
from .realtime import notify_update

# Generous per-user throttle on game actions to stop spam/abuse.
ACTION_LIMIT = rate_limit("action", limit=40, window=10)

User = get_user_model()


def lobby(request):
    # Optional filters for the open-games list.
    f_lang = request.GET.get("lang", "")
    f_rated = request.GET.get("rated", "")

    waiting = (
        Game.objects.filter(status=Game.WAITING)
        .exclude(players__player=request.user)
        .prefetch_related("players__player")
    )
    if f_lang in ("es", "en"):
        waiting = waiting.filter(language=f_lang)
    if f_rated in ("1", "0"):
        waiting = waiting.filter(rated=(f_rated == "1"))

    waiting_page = Paginator(waiting, 15).get_page(request.GET.get("wpage"))

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
    # Correspondence-style split: games awaiting my move vs. the opponent's.
    my_turn, my_waiting = [], []
    for g in mine:
        seat = g.current_seat
        if g.status == Game.ACTIVE and seat and seat.player_id == request.user.pk:
            my_turn.append(g)
        else:
            my_waiting.append(g)
    recent = (
        Game.objects.filter(status=Game.FINISHED)
        .select_related("winner")
        .prefetch_related("players__player")
    )
    recent_page = Paginator(recent, 12).get_page(request.GET.get("fpage"))

    leaders = User.objects.filter(is_guest=False).order_by("-rating")[:10]
    return render(request, "game/lobby.html", {
        "waiting": waiting_page, "active": active,
        "my_turn": my_turn, "my_waiting": my_waiting,
        "recent": recent_page, "leaders": leaders,
        "f_lang": f_lang, "f_rated": f_rated,
    })


def _language(request):
    lang = request.POST.get("language", "es")
    return lang if lang in ("es", "en") else "es"


# Allowed time controls as "initial_seconds,increment_seconds".
TIME_CONTROLS = {"0,0", "180,0", "300,0", "300,5", "600,5", "900,10", "1800,0"}


def _clock(request):
    raw = request.POST.get("clock", "0,0")
    if raw not in TIME_CONTROLS:
        raw = "0,0"
    initial, increment = (int(x) for x in raw.split(","))
    return initial, increment


@require_POST
@ACTION_LIMIT
def create_game(request):
    rated = request.POST.get("rated", "1") == "1"
    initial, increment = _clock(request)
    game = services.create_game(
        request.user, rated=rated, language=_language(request),
        clock_initial=initial, clock_increment=increment,
    )
    return redirect("game_detail", game_id=game.pk)


@require_POST
@ACTION_LIMIT
def quick_pair(request):
    initial, increment = _clock(request)
    game = services.quick_pair(
        request.user, language=_language(request),
        clock_initial=initial, clock_increment=increment,
    )
    notify_update(game.pk)
    return redirect("game_detail", game_id=game.pk)


@require_POST
@ACTION_LIMIT
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


def analysis(request, game_id):
    """Premium-only post-game analysis."""
    game = get_object_or_404(Game, pk=game_id)
    if not (request.user.is_authenticated and request.user.is_premium):
        return render(request, "game/analysis_locked.html", {"game": game}, status=200)
    if game.status not in (Game.FINISHED, Game.ABORTED):
        return redirect("game_detail", game_id=game.pk)
    return render(request, "game/analysis.html", {
        "game": game, "analysis": services.game_analysis(game),
    })


def game_state(request, game_id):
    """JSON bootstrap / polling fallback. Includes the caller's own rack."""
    game = get_object_or_404(Game, pk=game_id)
    return JsonResponse({
        "state": services.public_state(game),
        "rack": services.rack_for(game, request.user),
    })


@require_POST
@ACTION_LIMIT
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
@ACTION_LIMIT
def passturn(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.make_pass(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
@ACTION_LIMIT
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
@ACTION_LIMIT
def resign(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.resign(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
@ACTION_LIMIT
def flag(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.claim_time(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
@ACTION_LIMIT
def offer_draw(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.offer_draw(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
@ACTION_LIMIT
def respond_draw(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        accept = bool(json.loads(request.body or "{}").get("accept"))
    except ValueError:
        accept = False
    try:
        game = services.respond_draw(game, request.user, accept)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True})


@require_POST
@ACTION_LIMIT
def rematch(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    try:
        game = services.offer_rematch(game, request.user)
    except InvalidMove as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    notify_update(game.pk)
    return JsonResponse({"ok": True, "next_game_id": game.next_game_id})


def _error(request, message):
    return render(request, "game/error.html", {"message": message}, status=400)
