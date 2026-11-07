"""Template context shared across pages (navigation badges)."""

import re

from game.models import Challenge

from .models import Friendship, Notification


def social_badges(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and not user.is_guest):
        return {}
    return {
        "nav_friend_requests": Friendship.objects.filter(
            to_user=user, status=Friendship.PENDING).count(),
        "nav_challenges": Challenge.objects.filter(
            opponent=user, status=Challenge.PENDING).count(),
        "nav_notifications": Notification.objects.filter(
            user=user, is_read=False).count(),
    }


def seo(request):
    """Canonical + per-language (hreflang) URLs and analytics for the page."""
    from django.conf import settings
    canonical = request.build_absolute_uri(request.path)
    return {
        "seo_canonical": canonical,
        "seo_es": canonical + "?hl=es",
        "seo_en": canonical + "?hl=en",
        "analytics_domain": getattr(settings, "PLAUSIBLE_DOMAIN", ""),
    }


def error_reporting(request):
    """Browser error reporting to Jentry: same project as the backend.

    Only outside DEBUG and with a DSN, so local runs and tests send nothing.
    A DSN's public key is meant to be in the page; a legacy secret part, if
    one were ever configured, is stripped before it gets there.
    """
    from django.conf import settings
    dsn = getattr(settings, "SENTRY_DSN", "")
    if settings.DEBUG or not dsn:
        return {}
    return {
        "sentry_browser_dsn": re.sub(r"^(https?://[^:@/]+):[^@/]*@", r"\1@", dsn),
        "sentry_environment": getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        "sentry_release": getattr(settings, "SENTRY_RELEASE", ""),
    }
