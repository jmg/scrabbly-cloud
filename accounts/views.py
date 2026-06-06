from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from game.models import GamePlayer, Move

from . import social
from .forms import LoginForm, RegisterForm
from .models import Friendship
from .themes import THEMES, THEME_CODES, PREMIUM_THEMES

User = get_user_model()


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            email = form.cleaned_data.get("email", "")
            user = request.user
            # Upgrade the current guest account in place so its rating and
            # game history carry over. Otherwise create a fresh account.
            if user.is_authenticated and getattr(user, "is_guest", False):
                user.username = username
                user.email = email
                user.is_guest = False
                user.set_password(password)
                user.save()
            else:
                user = User.objects.create_user(
                    username=username, password=password, email=email
                )
            login(request, user)
            from billing.emails import send_welcome
            send_welcome(user)
            messages.success(request, _("¡Cuenta creada!"))
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
            messages.error(request, _("Usuario o contraseña inválidos."))
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

    # Friend/challenge controls for an authenticated visitor on someone else.
    if (request.user.is_authenticated and not request.user.is_guest
            and not user.is_bot):
        ctx["relationship"] = social.relationship(request.user, user)

    return render(request, "accounts/profile.html", ctx)


def _real_user(request):
    """The current non-guest user, or None."""
    u = request.user
    return u if (u.is_authenticated and not u.is_guest) else None


def friends(request):
    user = _real_user(request)
    if user is None:
        return redirect("login")
    return render(request, "accounts/friends.html", {
        "friends": social.friends_of(user),
        "incoming": social.incoming_requests(user),
        "outgoing": social.outgoing_requests(user),
    })


@require_POST
def friend_request(request):
    user = _real_user(request)
    if user is None:
        return redirect("login")
    username = (request.POST.get("username") or "").strip()
    target = User.objects.filter(username=username, is_guest=False, is_bot=False).first()
    if target is None or target == user:
        messages.error(request, _("No se encontró ese usuario."))
        return redirect("friends")

    # If the other side already sent a request, accept it instead of duplicating.
    reverse = Friendship.objects.filter(from_user=target, to_user=user).first()
    if reverse:
        reverse.status = Friendship.ACCEPTED
        reverse.save(update_fields=["status"])
        messages.success(request, _("¡Ahora son amigos!"))
    elif social.are_friends(user, target):
        messages.info(request, _("Ya son amigos."))
    else:
        Friendship.objects.get_or_create(from_user=user, to_user=target)
        messages.success(request, _("Solicitud enviada."))
    return redirect(request.POST.get("next") or "friends")


@require_POST
def friend_respond(request):
    user = _real_user(request)
    if user is None:
        return redirect("login")
    fr = Friendship.objects.filter(
        pk=request.POST.get("id"), to_user=user, status=Friendship.PENDING
    ).first()
    if fr:
        if request.POST.get("accept") == "1":
            fr.status = Friendship.ACCEPTED
            fr.save(update_fields=["status"])
            messages.success(request, _("¡Ahora son amigos!"))
        else:
            fr.delete()
            messages.info(request, _("Solicitud rechazada."))
    return redirect("friends")


@require_POST
def friend_remove(request):
    user = _real_user(request)
    if user is None:
        return redirect("login")
    from django.db.models import Q
    Friendship.objects.filter(
        Q(from_user=user, to_user_id=request.POST.get("id"))
        | Q(to_user=user, from_user_id=request.POST.get("id"))
    ).delete()
    messages.info(request, _("Amistad eliminada."))
    return redirect(request.POST.get("next") or "friends")


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
        messages.error(request, _("Ese tema es exclusivo de Premium. 👑"))
        return redirect("pricing")
    request.user.board_theme = theme
    request.user.save(update_fields=["board_theme"])
    messages.success(request, _("Tema actualizado."))
    return redirect("profile", username=request.user.username)
