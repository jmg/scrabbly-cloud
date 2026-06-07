"""Lightweight presence tracking for the 'online now' count.

We stamp ``last_seen`` at most once a minute per user (cheap) and count users
seen in the last few minutes, caching the total briefly.
"""

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .models import User

ONLINE_WINDOW = 300   # seconds a user counts as "online" after their last hit
TOUCH_EVERY = 60      # min seconds between last_seen writes per user


def touch(user):
    if not user.is_authenticated:
        return
    now = timezone.now()
    if user.last_seen is None or (now - user.last_seen).total_seconds() > TOUCH_EVERY:
        User.objects.filter(pk=user.pk).update(last_seen=now)
        user.last_seen = now


def online_count():
    n = cache.get("online_count")
    if n is None:
        cutoff = timezone.now() - timedelta(seconds=ONLINE_WINDOW)
        n = User.objects.filter(is_bot=False, last_seen__gte=cutoff).count()
        cache.set("online_count", n, 15)
    return n
