from django.conf import settings
from django.db import models


class Subscription(models.Model):
    """A record of a user's premium subscription with a payment provider."""

    ACTIVE = "active"
    CANCELED = "canceled"   # will not renew; entitlement runs to period end
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (ACTIVE, "Activa"),
        (CANCELED, "Cancelada"),
        (EXPIRED, "Expirada"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_code = models.CharField(max_length=20)
    provider = models.CharField(max_length=20)  # "mock" or "stripe"
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)

    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} · {self.plan_code} ({self.status})"
