"""Template context shared across pages (navigation badges)."""

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
