"""Auto-provision a guest account for anonymous visitors.

Like Lichess, you can browse and play without registering. The first time an
anonymous visitor hits the site we create a lightweight guest user and log them
in, so every request is backed by a real (rateable) account.
"""

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.utils import translation

User = get_user_model()


class GuestUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        skip = (
            path.startswith("/static/")
            or path.startswith("/admin/")
            or path.startswith("/ws/")
            or path.startswith("/api/")
            or path.startswith("/billing/")
            or path == "/robots.txt"
            or path == "/sitemap.xml"
        )
        if not skip and not request.user.is_authenticated:
            user = User.objects.create(
                username=f"guest_{uuid.uuid4().hex[:12]}",
                is_guest=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            login(request, user)
            request.user = user
        return self.get_response(request)


class QueryLanguageMiddleware:
    """Honour an explicit ``?hl=es|en`` for the request (and persist it).

    Lets us expose distinct per-language URLs for SEO (hreflang) on top of the
    cookie-based language switcher. Must run after LocaleMiddleware so it wins.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hl = request.GET.get("hl")
        valid = hl in dict(settings.LANGUAGES)
        if valid:
            translation.activate(hl)
            request.LANGUAGE_CODE = hl
        response = self.get_response(request)
        if valid:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, hl)
        return response
