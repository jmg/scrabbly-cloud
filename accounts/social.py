"""Helpers for the friend graph."""

from django.db.models import Q

from .models import Friendship, User


def friends_of(user):
    """Users who are accepted friends of ``user``."""
    rows = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user), status=Friendship.ACCEPTED
    ).select_related("from_user", "to_user")
    ids = [r.to_user_id if r.from_user_id == user.id else r.from_user_id for r in rows]
    return User.objects.filter(id__in=ids).order_by("-rating")


def are_friends(a, b):
    return Friendship.objects.filter(
        Q(from_user=a, to_user=b) | Q(from_user=b, to_user=a),
        status=Friendship.ACCEPTED,
    ).exists()


def incoming_requests(user):
    return Friendship.objects.filter(
        to_user=user, status=Friendship.PENDING
    ).select_related("from_user")


def outgoing_requests(user):
    return Friendship.objects.filter(
        from_user=user, status=Friendship.PENDING
    ).select_related("to_user")


def relationship(a, b):
    """Return 'self', 'friends', 'sent', 'incoming' or 'none' for a vs b."""
    if a.id == b.id:
        return "self"
    f = Friendship.objects.filter(
        Q(from_user=a, to_user=b) | Q(from_user=b, to_user=a)
    ).first()
    if f is None:
        return "none"
    if f.status == Friendship.ACCEPTED:
        return "friends"
    return "sent" if f.from_user_id == a.id else "incoming"
