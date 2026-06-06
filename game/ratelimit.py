"""A small fixed-window rate limiter backed by Django's cache.

Used to throttle game actions per user so nobody can spam the move endpoints.
Uses the shared Redis cache in production, local memory in development.
"""

from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(name, limit, window):
    """Allow at most ``limit`` calls per ``window`` seconds per user/IP."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            ident = request.user.pk if request.user.is_authenticated else (
                request.META.get("REMOTE_ADDR", "anon")
            )
            key = f"rl:{name}:{ident}"
            # cache.add only sets the key (with TTL) if absent, so the window
            # starts on the first hit and the TTL is not reset by later hits.
            if cache.add(key, 1, window):
                return view(request, *args, **kwargs)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.add(key, 1, window)
                count = 1
            if count > limit:
                return JsonResponse(
                    {"ok": False, "error": "Demasiadas acciones, esperá un momento."},
                    status=429,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
