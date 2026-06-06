from django.conf import settings
from django.db import models


class Game(models.Model):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"
    ABORTED = "aborted"
    STATUS_CHOICES = [
        (WAITING, "Esperando rival"),
        (ACTIVE, "En juego"),
        (FINISHED, "Terminada"),
        (ABORTED, "Abortada"),
    ]

    LANGUAGE_CHOICES = [("es", "Español"), ("en", "English")]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=WAITING)
    rated = models.BooleanField(default=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="es")
    max_players = models.PositiveSmallIntegerField(default=2)

    # Clock (Fischer style). clock_initial == 0 means an untimed game.
    clock_initial = models.PositiveIntegerField(default=0)    # seconds per player
    clock_increment = models.PositiveIntegerField(default=0)  # seconds added per move
    turn_started_at = models.DateTimeField(null=True, blank=True)

    # Set for games against the computer ("easy" | "medium" | "hard").
    ai_level = models.CharField(max_length=10, blank=True)

    board = models.JSONField(default=dict, blank=True)   # engine Board.serialize()
    bag = models.JSONField(default=list, blank=True)     # remaining bag letters
    turn_index = models.PositiveSmallIntegerField(default=0)
    consecutive_passes = models.PositiveSmallIntegerField(default=0)

    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="games_won",
    )
    # A pending draw offer during play, and a pending rematch offer afterwards.
    draw_offer_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    rematch_offer_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    next_game = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="previous_game",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def seats(self):
        return self.players.order_by("seat")

    @property
    def is_full(self):
        return self.players.count() >= self.max_players

    @property
    def has_clock(self):
        return self.clock_initial > 0

    @property
    def clock_label(self):
        if not self.has_clock:
            return "∞"
        return f"{self.clock_initial // 60}+{self.clock_increment}"

    @property
    def current_seat(self):
        seats = list(self.seats)
        if not seats:
            return None
        return seats[self.turn_index % len(seats)]

    def seat_for(self, user):
        return self.players.filter(player=user).first()

    def __str__(self):
        return f"Game #{self.pk} ({self.status})"


class GamePlayer(models.Model):
    """A seat at a game: a player, their rack and their running score."""

    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="players")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seats"
    )
    seat = models.PositiveSmallIntegerField(default=0)
    score = models.IntegerField(default=0)
    rack = models.JSONField(default=list, blank=True)
    time_left_ms = models.IntegerField(default=0)  # remaining clock, milliseconds

    result = models.CharField(max_length=4, blank=True)
    rating_before = models.IntegerField(null=True, blank=True)
    rating_after = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["seat"]
        unique_together = [("game", "player"), ("game", "seat")]

    @property
    def rating_delta(self):
        if self.rating_before is None or self.rating_after is None:
            return None
        return self.rating_after - self.rating_before

    def __str__(self):
        return f"{self.player} @ {self.game_id} (seat {self.seat})"


class Move(models.Model):
    PLAY = "play"
    PASS = "pass"
    EXCHANGE = "exchange"
    RESIGN = "resign"
    KIND_CHOICES = [
        (PLAY, "Jugada"), (PASS, "Paso"),
        (EXCHANGE, "Cambio"), (RESIGN, "Abandono"),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="moves"
    )
    number = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=PLAY)
    placements = models.JSONField(default=list, blank=True)
    words = models.JSONField(default=list, blank=True)
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Move {self.number} ({self.kind}) in game {self.game_id}"


class Challenge(models.Model):
    """A direct invitation from one user to play another with set conditions."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELED = "canceled"
    STATUS_CHOICES = [
        (PENDING, "Pendiente"), (ACCEPTED, "Aceptado"),
        (DECLINED, "Rechazado"), (CANCELED, "Cancelado"),
    ]

    challenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenges_sent")
    opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenges_received")
    language = models.CharField(max_length=5, default="es")
    rated = models.BooleanField(default=True)
    clock_initial = models.PositiveIntegerField(default=0)
    clock_increment = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    game = models.ForeignKey(
        Game, null=True, blank=True, on_delete=models.SET_NULL, related_name="from_challenge")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.challenger} → {self.opponent} ({self.status})"


class Puzzle(models.Model):
    """A 'find the best move' puzzle: a board + rack with a known top play."""

    language = models.CharField(max_length=5, default="es")
    board = models.JSONField(default=dict)      # engine Board.serialize()
    rack = models.JSONField(default=list)
    best_move = models.JSONField(default=list)  # placements data of the top play
    best_score = models.IntegerField(default=0)
    best_word = models.CharField(max_length=20, blank=True)
    date = models.DateField(null=True, blank=True, unique=True)  # set for the daily
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Puzzle #{self.pk} ({self.best_word} +{self.best_score})"


class PuzzleSolve(models.Model):
    """A user's best attempt at a puzzle."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="puzzle_solves")
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="solves")
    solved = models.BooleanField(default=False)
    best_score_achieved = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "puzzle")
