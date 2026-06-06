"""Auto-provision a guest account for anonymous visitors.

Like Lichess, you can browse and play without registering. The first time an
anonymous visitor hits the site we create a lightweight guest user and log them
in, so every request is backed by a real (rateable) account.
"""

import uuid

from django.contrib.auth import get_user_model, login

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
