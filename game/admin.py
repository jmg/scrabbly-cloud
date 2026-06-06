from django.contrib import admin

from .models import Game, GamePlayer, Move


class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "rated", "turn_index", "winner", "created_at")
    list_filter = ("status", "rated")
    inlines = [GamePlayerInline]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "number", "kind", "player", "points")
    list_filter = ("kind",)
