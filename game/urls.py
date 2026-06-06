from django.urls import path

from . import views

urlpatterns = [
    path("", views.lobby, name="lobby"),
    path("game/new/", views.create_game, name="create_game"),
    path("game/quick/", views.quick_pair, name="quick_pair"),
    path("game/ai/", views.create_ai_game, name="create_ai_game"),
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("game/<int:game_id>/join/", views.join_game, name="join_game"),
    path("game/<int:game_id>/state/", views.game_state, name="game_state"),
    path("game/<int:game_id>/analysis/", views.analysis, name="analysis"),
    path("game/<int:game_id>/play/", views.play, name="play"),
    path("game/<int:game_id>/pass/", views.passturn, name="passturn"),
    path("game/<int:game_id>/exchange/", views.exchange, name="exchange"),
    path("game/<int:game_id>/resign/", views.resign, name="resign"),
    path("game/<int:game_id>/flag/", views.flag, name="flag"),
    path("game/<int:game_id>/offer-draw/", views.offer_draw, name="offer_draw"),
    path("game/<int:game_id>/respond-draw/", views.respond_draw, name="respond_draw"),
    path("game/<int:game_id>/rematch/", views.rematch, name="rematch"),
]
