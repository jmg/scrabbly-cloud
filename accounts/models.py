from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

DEFAULT_RATING = 1500

# Free accounts may have at most this many games in progress at once.
FREE_CONCURRENT_GAMES = 3


class User(AbstractUser):
    """Custom user with a Glicko-ish/ELO rating and guest support.

    Guests are real (anonymous) accounts so they can hold a rating and appear
    in games, but they carry an unusable password and a generated username.
    """

    is_guest = models.BooleanField(default=False)
    rating = models.IntegerField(default=DEFAULT_RATING)
    games_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)

    # Premium subscription: active while premium_until is in the future.
    premium_until = models.DateTimeField(null=True, blank=True)
    board_theme = models.CharField(max_length=20, default="classic")

    @property
    def display_name(self):
        if self.is_guest:
            return f"Invitado-{self.pk}"
        return self.username

    @property
    def is_premium(self):
        return self.premium_until is not None and self.premium_until > timezone.now()

    @property
    def effective_theme(self):
        """The board theme actually applied (premium themes need a sub)."""
        from .themes import PREMIUM_THEMES
        if self.board_theme in PREMIUM_THEMES and not self.is_premium:
            return "classic"
        return self.board_theme or "classic"

    def __str__(self):
        return self.display_name
