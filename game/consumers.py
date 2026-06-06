import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from . import services
from .models import Game
from .realtime import broadcast_chat, group_name


class GameConsumer(AsyncWebsocketConsumer):
    """Live game socket: pushes board state and relays chat.

    Players and spectators share the same group. Each socket computes its own
    rack on update, so opponents/spectators never receive private tiles.
    """

    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group = group_name(self.game_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_state()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except ValueError:
            return
        if data.get("type") == "chat":
            text = (data.get("text") or "").strip()[:500]
            user = self.scope.get("user")
            if text and user and user.is_authenticated:
                await database_sync_to_async(broadcast_chat)(
                    self.game_id, user.display_name, text
                )

    async def game_update(self, event):
        await self.send_state()

    async def game_chat(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat", "author": event["author"], "text": event["text"],
        }))

    async def send_state(self):
        payload = await self._load_state()
        if payload is not None:
            await self.send(text_data=json.dumps({"type": "state", **payload}))

    @database_sync_to_async
    def _load_state(self):
        try:
            game = Game.objects.get(pk=self.game_id)
        except Game.DoesNotExist:
            return None
        user = self.scope.get("user")
        rack = services.rack_for(game, user) if user and user.is_authenticated else []
        return {"state": services.public_state(game), "rack": rack}
