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
    is_bot = models.BooleanField(default=False)
    rating = models.IntegerField(default=DEFAULT_RATING)
    games_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)

    # Premium subscription: active while premium_until is in the future.
    premium_until = models.DateTimeField(null=True, blank=True)
    premium_tier = models.CharField(max_length=10, blank=True)  # "gold" | "diamond"
    has_used_trial = models.BooleanField(default=False)
    board_theme = models.CharField(max_length=20, default="classic")
    email_opt_in = models.BooleanField(default=True)  # receipts & notifications

    @property
    def display_name(self):
        if self.is_guest:
            return f"Invitado-{self.pk}"
        return self.username

    @property
    def is_premium(self):
        return self.premium_until is not None and self.premium_until > timezone.now()

    @property
    def tier(self):
        """Active tier name: 'gold', 'diamond' or '' when not premium."""
        return self.premium_tier if self.is_premium else ""

    def has_perk(self, perk):
        from billing.plans import tier_has_perk
        return self.is_premium and tier_has_perk(self.premium_tier, perk)

    @property
    def effective_theme(self):
        """The board theme actually applied (premium themes need the perk)."""
        from .themes import PREMIUM_THEMES
        if self.board_theme in PREMIUM_THEMES and not self.has_perk("themes"):
            return "classic"
        return self.board_theme or "classic"

    def __str__(self):
        return self.display_name


class Friendship(models.Model):
    """A friend relationship/request between two users.

    A single row per direction: it starts ``pending`` (a request) and becomes
    ``accepted`` once the recipient confirms. Two users are friends if an
    accepted row exists in either direction.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    STATUS_CHOICES = [(PENDING, "Pendiente"), (ACCEPTED, "Aceptada")]

    from_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="friendship_sent")
    to_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="friendship_received")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"


class Notification(models.Model):
    """A small in-app notification, also pushed live over WebSocket."""

    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="notifications")
    text = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.text}"

