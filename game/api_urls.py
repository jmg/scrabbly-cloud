from django.urls import path

from . import api

urlpatterns = [
    path("games/", api.games, name="api_games"),
    path("games/<int:game_id>/", api.game, name="api_game"),
    path("leaderboard/", api.leaderboard, name="api_leaderboard"),
    path("players/<str:username>/", api.player, name="api_player"),
]
