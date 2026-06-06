from django.conf import settings
from django.db import models


class Subscription(models.Model):
    """A record of a user's premium subscription with a payment provider."""

    ACTIVE = "active"
    CANCELED = "canceled"   # will not renew; entitlement runs to period end
    PAST_DUE = "past_due"   # a payment failed; retrying (dunning)
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (ACTIVE, "Activa"),
        (CANCELED, "Cancelada"),
        (PAST_DUE, "Pago pendiente"),
        (EXPIRED, "Expirada"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_code = models.CharField(max_length=20)
    tier = models.CharField(max_length=10, blank=True)
    provider = models.CharField(max_length=20)  # "mock" or "stripe"
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    coupon_code = models.CharField(max_length=40, blank=True)
    is_trial = models.BooleanField(default=False)

    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} · {self.plan_code} ({self.status})"


class Coupon(models.Model):
    """A discount/bonus code. Drives the mock flow and bonus trial days; with
    Stripe, native promotion codes are also accepted at Checkout."""

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)
    percent_off = models.PositiveSmallIntegerField(default=0)   # informational
    free_days = models.PositiveIntegerField(default=0)          # bonus entitlement
    active = models.BooleanField(default=True)
    max_redemptions = models.PositiveIntegerField(default=0)    # 0 = unlimited
    times_redeemed = models.PositiveIntegerField(default=0)
    stripe_coupon_id = models.CharField(max_length=80, blank=True)

    def is_redeemable(self):
        if not self.active:
            return False
        return self.max_redemptions == 0 or self.times_redeemed < self.max_redemptions

    def __str__(self):
        return self.code


class GiftCode(models.Model):
    """A one-time gift of Premium that a recipient redeems for a code."""

    code = models.CharField(max_length=20, unique=True)
    plan_code = models.CharField(max_length=30)
    tier = models.CharField(max_length=10)
    days = models.PositiveIntegerField()
    purchaser = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="gifts_bought",
    )
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="gifts_redeemed",
    )
    redeemed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_redeemed(self):
        return self.redeemed_by_id is not None

    def __str__(self):
        return f"Gift {self.code} ({self.tier})"
