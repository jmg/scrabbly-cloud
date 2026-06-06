from django.contrib.auth.models import AbstractUser
from django.db import models

DEFAULT_RATING = 1500


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

    @property
    def display_name(self):
        if self.is_guest:
            return f"Invitado-{self.pk}"
        return self.username

    def __str__(self):
        return self.display_name
