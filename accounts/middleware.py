"""Presence and language, on every request.

Like Lichess, you can browse and play without registering. Browsing needs no
account at all: a guest is created only when a visitor sits down to play
(accounts.views.ensure_guest). Creating one per anonymous hit let anything that
doesn't send the session cookie back (crawlers, monitors, a script) fill the
users and sessions tables and the DB's connection slots.
"""

from django.conf import settings
from django.utils import translation


class GuestUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            from .presence import touch
            touch(request.user)
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
