"""Payment providers.

``get_provider()`` returns the Stripe provider when STRIPE_SECRET_KEY is set,
otherwise a mock provider that activates the subscription immediately. The mock
exists so the whole premium flow is usable in development and tests without any
payment credentials.
"""

from django.conf import settings
from django.urls import reverse

from . import service
from .plans import TRIAL_DAYS, get_plan


class MockProvider:
    """Dev/demo provider: 'paying' instantly grants premium."""

    code = "mock"

    def create_checkout(self, user, plan_code, request, *, trial=False, coupon=None):
        bonus = (coupon.free_days if coupon else 0)
        days = TRIAL_DAYS if trial else None
        service.activate(
            user, plan_code, self.code,
            period_days=days, bonus_days=bonus, is_trial=trial,
            coupon_code=(coupon.code if coupon else ""),
        )
        service.redeem_coupon(coupon)
        return request.build_absolute_uri(reverse("billing_success") + "?mock=1")

    def portal(self, user, request):
        return request.build_absolute_uri(reverse("billing_manage"))

    def cancel(self, user):
        service.cancel(user)


class StripeProvider:
    """Real Stripe Checkout (subscription mode) + webhook activation."""

    code = "stripe"

    def __init__(self):
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.stripe = stripe

    def create_checkout(self, user, plan_code, request, *, trial=False, coupon=None):
        plan = get_plan(plan_code)
        success = request.build_absolute_uri(reverse("billing_success"))
        cancel = request.build_absolute_uri(reverse("pricing"))
        metadata = {"user_id": str(user.pk), "plan_code": plan_code}
        price_data = {
            "currency": plan["currency"],
            "unit_amount": plan["amount"],
            "product_data": {"name": "Scrabbly " + plan["name"]},
        }
        if plan.get("lifetime"):
            # One-time payment, no recurring billing.
            params = dict(
                mode="payment",
                success_url=success + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel,
                client_reference_id=str(user.pk),
                metadata=metadata,
                line_items=[{"quantity": 1, "price_data": price_data}],
            )
        else:
            price_data["recurring"] = {"interval": plan["interval"]}
            sub_data = {"metadata": metadata}
            if trial:
                sub_data["trial_period_days"] = TRIAL_DAYS
            params = dict(
                mode="subscription",
                success_url=success + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel,
                client_reference_id=str(user.pk),
                metadata=metadata,
                subscription_data=sub_data,
                allow_promotion_codes=True,
                line_items=[{"quantity": 1, "price_data": price_data}],
            )
            if coupon and coupon.stripe_coupon_id:
                params.pop("allow_promotion_codes")
                params["discounts"] = [{"coupon": coupon.stripe_coupon_id}]
        session = self.stripe.checkout.Session.create(**params)
        return session.url

    def create_gift_checkout(self, user, gift_plan_code, request):
        from .plans import GIFT_PLANS
        plan = GIFT_PLANS[gift_plan_code]
        success = request.build_absolute_uri(reverse("billing_success"))
        cancel = request.build_absolute_uri(reverse("gift"))
        session = self.stripe.checkout.Session.create(
            mode="payment",
            success_url=success,
            cancel_url=cancel,
            client_reference_id=str(user.pk),
            metadata={"kind": "gift", "user_id": str(user.pk), "gift_plan": gift_plan_code},
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": plan["currency"],
                    "unit_amount": plan["amount"],
                    "product_data": {"name": "Scrabbly regalo · " + plan["name"]},
                },
            }],
        )
        return session.url

    def portal(self, user, request):
        sub = service.active_subscription(user)
        customer = sub.provider_customer_id if sub else ""
        if not customer:
            return request.build_absolute_uri(reverse("billing_manage"))
        session = self.stripe.billing_portal.Session.create(
            customer=customer,
            return_url=request.build_absolute_uri(reverse("billing_manage")),
        )
        return session.url

    def cancel(self, user):
        sub = service.active_subscription(user)
        if sub and sub.provider_subscription_id:
            try:
                self.stripe.Subscription.modify(
                    sub.provider_subscription_id, cancel_at_period_end=True
                )
            except Exception:
                pass
        service.cancel(user)

    def construct_event(self, payload, sig_header):
        return self.stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )


def get_provider():
    if getattr(settings, "STRIPE_SECRET_KEY", ""):
        return StripeProvider()
    return MockProvider()
