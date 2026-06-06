"""Provider-agnostic subscription logic.

The HTTP views and the Stripe webhook both funnel through ``activate`` /
``cancel`` so premium entitlement is granted in exactly one place.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Subscription
from .plans import get_plan


def activate(user, plan_code, provider, *, customer_id="", subscription_id="",
             period_days=None):
    """Grant/extend premium for ``user`` and upsert their Subscription record."""
    plan = get_plan(plan_code)
    if plan is None:
        raise ValueError(f"Unknown plan: {plan_code}")
    days = period_days if period_days is not None else plan["days"]

    now = timezone.now()
    base = user.premium_until if (user.premium_until and user.premium_until > now) else now
    user.premium_until = base + timedelta(days=days)
    user.save(update_fields=["premium_until"])

    sub, _ = Subscription.objects.update_or_create(
        user=user,
        provider=provider,
        provider_subscription_id=subscription_id or "",
        defaults={
            "plan_code": plan_code,
            "status": Subscription.ACTIVE,
            "provider_customer_id": customer_id,
            "current_period_end": user.premium_until,
        },
    )
    return sub


def cancel(user):
    """Stop auto-renew. Premium stays until the current period ends."""
    Subscription.objects.filter(user=user, status=Subscription.ACTIVE).update(
        status=Subscription.CANCELED
    )


def active_subscription(user):
    return user.subscriptions.filter(status=Subscription.ACTIVE).first()
