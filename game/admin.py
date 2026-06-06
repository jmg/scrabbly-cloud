from django.contrib import admin

from .models import (
    Arena, ArenaPlayer, Challenge, Game, GamePlayer, Move, Puzzle, PuzzleSolve,
)


class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "rated", "turn_index", "winner", "arena", "created_at")
    list_filter = ("status", "rated")
    inlines = [GamePlayerInline]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "number", "kind", "player", "points")
    list_filter = ("kind",)


class ArenaPlayerInline(admin.TabularInline):
    model = ArenaPlayer
    extra = 0
    readonly_fields = ("user", "score", "games", "waiting", "joined_at")


@admin.register(Arena)
class ArenaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "language", "starts_at", "duration_min",
                    "rated", "created_by")
    list_filter = ("language", "rated")
    search_fields = ("name",)
    inlines = [ArenaPlayerInline]


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "challenger", "opponent", "status", "rated", "created_at")
    list_filter = ("status", "rated")
    search_fields = ("challenger__username", "opponent__username")


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("id", "language", "best_word", "best_score", "date", "created_at")
    list_filter = ("language",)


@admin.register(PuzzleSolve)
class PuzzleSolveAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "puzzle", "solved", "best_score_achieved")
    list_filter = ("solved",)
