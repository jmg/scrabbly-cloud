"""Provider-agnostic subscription logic.

The HTTP views and the Stripe webhook both funnel through ``activate`` /
``cancel`` so premium entitlement is granted in exactly one place.
"""

import secrets
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from .models import Coupon, GiftCode, Subscription
from .plans import GIFT_PLANS, get_plan


def activate(user, plan_code, provider, *, customer_id="", subscription_id="",
             period_days=None, bonus_days=0, is_trial=False, coupon_code=""):
    """Grant/extend premium for ``user`` and upsert their Subscription record."""
    plan = get_plan(plan_code)
    if plan is None:
        raise ValueError(f"Unknown plan: {plan_code}")
    days = (period_days if period_days is not None else plan["days"]) + bonus_days

    now = timezone.now()
    base = user.premium_until if (user.premium_until and user.premium_until > now) else now
    user.premium_until = base + timedelta(days=days)
    user.premium_tier = plan["tier"]
    user.save(update_fields=["premium_until", "premium_tier"])

    sub, _ = Subscription.objects.update_or_create(
        user=user,
        provider=provider,
        provider_subscription_id=subscription_id or "",
        defaults={
            "plan_code": plan_code,
            "tier": plan["tier"],
            "status": Subscription.ACTIVE,
            "provider_customer_id": customer_id,
            "current_period_end": user.premium_until,
            "coupon_code": coupon_code,
            "is_trial": is_trial,
        },
    )
    from .emails import send_receipt
    send_receipt(user, sub)
    return sub


def cancel(user):
    """Stop auto-renew. Premium stays until the current period ends."""
    Subscription.objects.filter(user=user, status=Subscription.ACTIVE).update(
        status=Subscription.CANCELED
    )


def active_subscription(user):
    return user.subscriptions.filter(status=Subscription.ACTIVE).first()


def validate_coupon(code):
    """Return a redeemable Coupon for ``code`` (case-insensitive) or None."""
    if not code:
        return None
    coupon = Coupon.objects.filter(code__iexact=code.strip()).first()
    if coupon and coupon.is_redeemable():
        return coupon
    return None


def redeem_coupon(coupon):
    if coupon:
        Coupon.objects.filter(pk=coupon.pk).update(
            times_redeemed=F("times_redeemed") + 1
        )


def grant_premium(user, tier, days, *, source="gift"):
    """Extend a user's premium entitlement without a recurring subscription."""
    now = timezone.now()
    base = user.premium_until if (user.premium_until and user.premium_until > now) else now
    user.premium_until = base + timedelta(days=days)
    user.premium_tier = tier
    user.save(update_fields=["premium_until", "premium_tier"])
    Subscription.objects.create(
        user=user, plan_code=source, tier=tier, provider=source,
        status=Subscription.CANCELED, current_period_end=user.premium_until,
    )


def _gift_code():
    return "GIFT-" + secrets.token_hex(4).upper()


def create_gift(purchaser, gift_plan_code):
    plan = GIFT_PLANS.get(gift_plan_code)
    if plan is None:
        raise ValueError("Unknown gift plan")
    code = _gift_code()
    while GiftCode.objects.filter(code=code).exists():
        code = _gift_code()
    gift = GiftCode.objects.create(
        code=code, plan_code=gift_plan_code, tier=plan["tier"],
        days=plan["days"], purchaser=purchaser,
    )
    from .emails import send_gift_purchased
    send_gift_purchased(purchaser, gift)
    return gift


def redeem_gift(user, code):
    gift = GiftCode.objects.filter(code__iexact=(code or "").strip()).first()
    if gift is None or gift.is_redeemed:
        return None
    grant_premium(user, gift.tier, gift.days, source="gift")
    gift.redeemed_by = user
    gift.redeemed_at = timezone.now()
    gift.save(update_fields=["redeemed_by", "redeemed_at"])
    return gift
