from django.urls import re_path

from accounts.consumers import NotificationConsumer

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/game/(?P<game_id>\d+)/$", consumers.GameConsumer.as_asgi()),
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
]
