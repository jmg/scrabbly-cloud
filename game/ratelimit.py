"""A small fixed-window rate limiter backed by Django's cache.

Used to throttle game actions per user so nobody can spam the move endpoints.
Uses the shared Redis cache in production, local memory in development.
"""

import ipaddress
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def client_ip(request):
    """The address limits count, as the one proxy in front (Traefik) saw it.

    REMOTE_ADDR is that proxy, the same for everybody. A proxy APPENDS the peer
    it saw to X-Forwarded-For, so the LAST entry is the only one a client can't
    write; the first is whatever they claim, which is why Daphne's
    --proxy-headers (it reads the first) isn't an option. Daphne and Django
    drop header names with underscores, so X_Forwarded_For can't pose as it.

    An IPv6 client counts by its /64: one host gets a whole /64 and could spend
    a fresh bucket per address.
    """
    raw = request.META.get("HTTP_X_FORWARDED_FOR", "").rsplit(",", 1)[-1].strip()
    try:
        addr = ipaddress.ip_address(raw)
        if addr.version == 6:
            if addr.ipv4_mapped:
                return str(addr.ipv4_mapped)
            return str(ipaddress.ip_network(f"{addr}/64", strict=False))
        return str(addr)
    except ValueError:
        return request.META.get("REMOTE_ADDR", "anon")


def rate_limit(name, limit, window):
    """Allow at most ``limit`` calls per ``window`` seconds per user/IP."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            ident = request.user.pk if request.user.is_authenticated else client_ip(request)
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
