from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import get_object_or_404, redirect, render

from game.models import GamePlayer

from .forms import LoginForm, RegisterForm

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
    return render(request, "accounts/profile.html", {
        "profile_user": user, "seats": seats,
        "win_rate": win_rate, "form": form,
    })
