from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from game.models import GamePlayer, Move

from .forms import LoginForm, RegisterForm
from .themes import THEMES, THEME_CODES, PREMIUM_THEMES

User = get_user_model()


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = request.user
            # Upgrade the current guest account in place so its rating and
            # game history carry over. Otherwise create a fresh account.
            if user.is_authenticated and getattr(user, "is_guest", False):
                user.username = username
                user.is_guest = False
                user.set_password(password)
                user.save()
            else:
                user = User.objects.create_user(
                    username=username, password=password
                )
            login(request, user)
            messages.success(request, "¡Cuenta creada!")
            return redirect("lobby")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            if user is not None and not user.is_guest:
                login(request, user)
                return redirect("lobby")
            messages.error(request, "Usuario o contraseña inválidos.")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("lobby")


def profile(request, username):
    user = get_object_or_404(User, username=username)
    seats = list(
        GamePlayer.objects.filter(player=user, game__status="finished")
        .select_related("game")
        .order_by("-game__created_at")[:25]
    )
    decided = user.wins + user.losses
    win_rate = round(100 * user.wins / decided) if decided else None
    # Recent form: most-recent-first list of results for coloured dots.
    form = [s.result for s in seats if s.result][:10]

    ctx = {
        "profile_user": user, "seats": seats,
        "win_rate": win_rate, "form": form,
    }

    # Advanced stats require the 'stats' perk (Gold+).
    if user.has_perk("stats"):
        ctx["advanced"] = _advanced_stats(user)

    # Board-theme picker is shown to the profile owner.
    if request.user == user and not user.is_guest:
        ctx["themes"] = THEMES
        ctx["current_theme"] = user.board_theme
        ctx["can_use_premium_themes"] = user.has_perk("themes")

    return render(request, "accounts/profile.html", ctx)


def _advanced_stats(user):
    """Rating curve and scoring insight (premium feature)."""
    chrono = list(
        GamePlayer.objects.filter(player=user, rating_after__isnull=False)
        .order_by("game__created_at")
        .values_list("rating_before", "rating_after")
    )
    history = []
    if chrono:
        history.append(chrono[0][0])
        history += [after for _before, after in chrono]

    plays = list(
        Move.objects.filter(player=user, kind=Move.PLAY).values_list("points", flat=True)
    )
    best_score = (
        GamePlayer.objects.filter(player=user)
        .order_by("-score").values_list("score", flat=True).first()
    )
    best_word = (
        Move.objects.filter(player=user, kind=Move.PLAY)
        .order_by("-points").values_list("words", "points").first()
    )
    return {
        "history": history,
        "spark": _sparkline(history),
        "avg_play": round(sum(plays) / len(plays), 1) if plays else None,
        "total_plays": len(plays),
        "best_score": best_score,
        "best_word": best_word,
    }


def _sparkline(values, w=260, h=48):
    """Tiny inline-SVG polyline of the rating history."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    n = len(values) - 1
    pts = " ".join(
        f"{(i / n) * w:.1f},{h - ((v - lo) / span) * (h - 6) - 3:.1f}"
        for i, v in enumerate(values)
    )
    from django.utils.safestring import mark_safe
    return mark_safe(
        f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg"><polyline fill="none" '
        f'stroke="#629924" stroke-width="2" points="{pts}"/></svg>'
    )


@require_POST
def set_theme(request):
    if not request.user.is_authenticated or request.user.is_guest:
        return redirect("login")
    theme = request.POST.get("theme", "classic")
    if theme not in THEME_CODES:
        theme = "classic"
    if theme in PREMIUM_THEMES and not request.user.has_perk("themes"):
        messages.error(request, "Ese tema es exclusivo de Premium. 👑")
        return redirect("pricing")
    request.user.board_theme = theme
    request.user.save(update_fields=["board_theme"])
    messages.success(request, "Tema actualizado.")
    return redirect("profile", username=request.user.username)
