import json

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.contrib import messages
from django.db.models import Q
from django.utils.translation import gettext as _

from . import services
from .engine import InvalidMove
from .models import Challenge, Game
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

    leaders = User.objects.filter(is_guest=False, is_bot=False).order_by("-rating")[:10]

    incoming_ch, outgoing_ch = [], []
    if request.user.is_authenticated and not request.user.is_guest:
        incoming_ch = list(
            Challenge.objects.filter(opponent=request.user, status=Challenge.PENDING)
            .select_related("challenger"))
        outgoing_ch = list(
            Challenge.objects.filter(challenger=request.user)
            .filter(Q(status=Challenge.PENDING) | Q(status=Challenge.ACCEPTED))
            .select_related("opponent", "game")[:10])

    return render(request, "game/lobby.html", {
        "waiting": waiting_page, "active": active,
        "my_turn": my_turn, "my_waiting": my_waiting,
        "recent": recent_page, "leaders": leaders,
        "f_lang": f_lang, "f_rated": f_rated,
        "incoming_challenges": incoming_ch, "outgoing_challenges": outgoing_ch,
    })


def arenas(request):
    from .models import Arena
    now_list = list(Arena.objects.all()[:40])
    live = [a for a in now_list if a.state == "active"]
    upcoming = [a for a in now_list if a.state == "pending"]
    finished = [a for a in now_list if a.state == "finished"][:10]
    return render(request, "game/arenas.html", {
        "live": live, "upcoming": upcoming, "finished": finished,
    })


@require_POST
@ACTION_LIMIT
def arena_create(request):
    from datetime import timedelta
    from django.utils import timezone
    from .models import Arena
    if not request.user.is_authenticated or request.user.is_guest:
        return redirect("login")
    name = (request.POST.get("name") or "").strip()[:80] or _("Arena")
    try:
        duration = max(5, min(180, int(request.POST.get("duration", "30"))))
        delay = max(0, min(60, int(request.POST.get("delay", "0"))))
    except ValueError:
        duration, delay = 30, 0
    initial, increment = _clock(request)
    arena = Arena.objects.create(
        name=name, language=_language(request),
        rated=request.POST.get("rated") == "1",
        clock_initial=initial or 300, clock_increment=increment,
        starts_at=timezone.now() + timedelta(minutes=delay),
        duration_min=duration, created_by=request.user,
    )
    return redirect("arena_detail", arena_id=arena.pk)


def arena_detail(request, arena_id):
    from .models import Arena, ArenaPlayer
    arena = get_object_or_404(Arena, pk=arena_id)
    standings = list(
        ArenaPlayer.objects.filter(arena=arena).select_related("user"))
    joined = False
    if request.user.is_authenticated:
        joined = any(p.user_id == request.user.pk for p in standings)
    return render(request, "game/arena.html", {
        "arena": arena, "standings": standings, "state": arena.state,
        "joined": joined,
    })


@require_POST
@ACTION_LIMIT
def arena_join(request, arena_id):
    from .models import Arena, ArenaPlayer
    arena = get_object_or_404(Arena, pk=arena_id)
    if not request.user.is_authenticated or request.user.is_guest:
        return redirect("login")
    if arena.state != "finished":
        ArenaPlayer.objects.get_or_create(arena=arena, user=request.user)
    return redirect("arena_detail", arena_id=arena.pk)


@require_POST
@ACTION_LIMIT
def arena_leave(request, arena_id):
    from .models import ArenaPlayer
    ArenaPlayer.objects.filter(arena_id=arena_id, user=request.user, games=0).delete()
    return redirect("arena_detail", arena_id=arena_id)


@ACTION_LIMIT
def arena_play(request, arena_id):
    from .models import Arena
    arena = get_object_or_404(Arena, pk=arena_id)
    if not request.user.is_authenticated or request.user.is_guest:
        return redirect("login")
    kind, game = services.arena_next(arena, request.user)
    if kind == "game":
        notify_update(game.pk)
        return redirect("game_detail", game_id=game.pk)
    if kind == "not_joined":
        return redirect("arena_detail", arena_id=arena.pk)
    if kind == "closed":
        messages.info(request, _("El torneo no está activo."))
        return redirect("arena_detail", arena_id=arena.pk)
    # waiting: this page auto-retries pairing until an opponent appears.
    return render(request, "game/arena_waiting.html", {"arena": arena})


def puzzles_index(request):
    from .models import PuzzleSolve
    solved = 0
    if request.user.is_authenticated and not request.user.is_guest:
        solved = PuzzleSolve.objects.filter(user=request.user, solved=True).count()
    return render(request, "game/puzzles.html", {"solved_count": solved})


def puzzle_daily(request):
    from . import puzzles
    lang = request.GET.get("lang", "es")
    p = puzzles.get_daily(lang if lang in ("es", "en") else "es")
    if p is None:
        return _error(request, _("No se pudo generar el puzzle. Probá de nuevo."))
    return redirect("puzzle_detail", puzzle_id=p.pk)


@require_POST
@ACTION_LIMIT
def puzzle_new(request):
    from . import puzzles
    p = puzzles.new_training_puzzle(_language(request))
    if p is None:
        return _error(request, _("No se pudo generar el puzzle. Probá de nuevo."))
    return redirect("puzzle_detail", puzzle_id=p.pk)


def puzzle_detail(request, puzzle_id):
    from .models import Puzzle
    from .engine import Board, get_ruleset
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    board = Board.deserialize(puzzle.board)
    state = {
        "id": puzzle.pk,
        "grid": {f"{r},{c}": l for (r, c), l in board.grid.items()},
        "blanks": [list(b) for b in board.blanks],
        "rack": puzzle.rack,
        "points": get_ruleset(puzzle.language).points,
        "best_score": puzzle.best_score,
    }
    return render(request, "game/puzzle.html", {
        "puzzle": puzzle, "state_json": json.dumps(state),
    })


@require_POST
@ACTION_LIMIT
def puzzle_solve(request, puzzle_id):
    from . import puzzles
    from .models import Puzzle, PuzzleSolve
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    try:
        placements = json.loads(request.body or "{}").get("placements", [])
        score = puzzles.evaluate(puzzle, placements)
    except (InvalidMove, ValueError, KeyError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    solved = score >= puzzle.best_score
    if request.user.is_authenticated and not request.user.is_guest:
        rec, _created = PuzzleSolve.objects.get_or_create(
            user=request.user, puzzle=puzzle)
        if score > rec.best_score_achieved:
            rec.best_score_achieved = score
        rec.solved = rec.solved or solved
        rec.save()
    return JsonResponse({
        "ok": True, "your_score": score, "best_score": puzzle.best_score,
        "solved": solved,
    })


def puzzle_reveal(request, puzzle_id):
    from .models import Puzzle
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    return JsonResponse({
        "best_move": puzzle.best_move, "best_word": puzzle.best_word,
        "best_score": puzzle.best_score,
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
def create_ai_game(request):
    level = request.POST.get("level", "medium")
    try:
        game = services.create_ai_game(request.user, level=level, language=_language(request))
    except InvalidMove as exc:
        return _error(request, str(exc))
    return redirect("game_detail", game_id=game.pk)


@require_POST
@ACTION_LIMIT
def challenge_create(request):
    user = request.user
    if not user.is_authenticated or user.is_guest:
        return redirect("login")
    opponent = User.objects.filter(
        username=(request.POST.get("opponent") or "").strip(),
        is_guest=False, is_bot=False,
    ).first()
    if opponent is None or opponent == user:
        messages.error(request, _("No se encontró ese usuario."))
        return redirect("friends")
    initial, increment = _clock(request)
    Challenge.objects.create(
        challenger=user, opponent=opponent,
        language=_language(request), rated=request.POST.get("rated") == "1",
        clock_initial=initial, clock_increment=increment,
    )
    from accounts.notifications import notify
    from django.urls import reverse
    notify(opponent, _("%(u)s te desafió a una partida.") % {"u": user.display_name},
           reverse("lobby"))
    messages.success(request, _("Desafío enviado."))
    return redirect(request.POST.get("next") or "lobby")


@require_POST
@ACTION_LIMIT
def challenge_respond(request):
    user = request.user
    ch = get_object_or_404(
        Challenge, pk=request.POST.get("id"), opponent=user, status=Challenge.PENDING)
    from accounts.notifications import notify
    if request.POST.get("accept") == "1":
        try:
            game = services.accept_challenge(ch)
        except InvalidMove as exc:
            return _error(request, str(exc))
        notify_update(game.pk)
        notify(ch.challenger,
               _("%(u)s aceptó tu desafío. ¡A jugar!") % {"u": user.display_name},
               f"/game/{game.pk}/")
        return redirect("game_detail", game_id=game.pk)
    ch.status = Challenge.DECLINED
    ch.save(update_fields=["status"])
    notify(ch.challenger, _("%(u)s rechazó tu desafío.") % {"u": user.display_name})
    messages.info(request, _("Desafío rechazado."))
    return redirect("lobby")


@require_POST
@ACTION_LIMIT
def challenge_cancel(request):
    Challenge.objects.filter(
        pk=request.POST.get("id"), challenger=request.user, status=Challenge.PENDING
    ).update(status=Challenge.CANCELED)
    return redirect(request.POST.get("next") or "lobby")


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
    if not (request.user.is_authenticated and request.user.has_perk("analysis")):
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
    game = services.maybe_play_bot(game)
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
    game = services.maybe_play_bot(game)
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
    game = services.maybe_play_bot(game)
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
