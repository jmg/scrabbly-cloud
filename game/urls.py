from django.urls import path

from . import views

urlpatterns = [
    path("", views.lobby, name="lobby"),
    path("game/new/", views.create_game, name="create_game"),
    path("game/quick/", views.quick_pair, name="quick_pair"),
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("game/<int:game_id>/join/", views.join_game, name="join_game"),
    path("game/<int:game_id>/state/", views.game_state, name="game_state"),
    path("game/<int:game_id>/play/", views.play, name="play"),
    path("game/<int:game_id>/pass/", views.passturn, name="passturn"),
    path("game/<int:game_id>/exchange/", views.exchange, name="exchange"),
    path("game/<int:game_id>/resign/", views.resign, name="resign"),
    path("game/<int:game_id>/flag/", views.flag, name="flag"),
]
