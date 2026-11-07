"""Create + live-push in-app notifications."""

import sentry_sdk
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def user_group(user_id):
    return f"user_{user_id}"


def notify(user, text, url=""):
    """Persist a notification and best-effort push it to the user's sockets."""
    if user is None or getattr(user, "is_guest", False):
        return None
    note = Notification.objects.create(user=user, text=text, url=url)
    layer = get_channel_layer()
    if layer is not None:
        try:
            async_to_sync(layer.group_send)(
                user_group(user.id),
                {"type": "notify", "text": text, "url": url},
            )
        except Exception:
            # The notification is saved; only the live push failed (channel
            # layer / Redis down). Don't break the caller, but report it.
            sentry_sdk.capture_exception()
    return note
