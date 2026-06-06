"""Helpers to push updates to connected clients over Channels."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def group_name(game_id):
    return f"game_{game_id}"


def notify_update(game_id):
    """Tell every socket watching a game to refresh its state."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group_name(game_id), {"type": "game.update"})


def broadcast_chat(game_id, author, text):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group_name(game_id),
        {"type": "game.chat", "author": author, "text": text},
    )
