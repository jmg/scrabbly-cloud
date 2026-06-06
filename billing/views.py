from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import service
from .plans import (
    GIFT_PLANS, PLANS, TIERS, TRIAL_DAYS, get_plan, price_display,
)
from .providers import get_provider


def _is_mock():
    return not bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def _tier_cards():
    """Group plans by tier for the pricing page."""
    cards = []
    for tier_code, tier in TIERS.items():
        plans = [
            {"code": code, "price": price_display(p), **p}
            for code, p in PLANS.items() if p["tier"] == tier_code
        ]
        cards.append({"code": tier_code, "name": tier["name"],
                      "perks": tier["perks"], "plans": plans})
    return cards


def pricing(request):
    user = request.user
    return render(request, "billing/pricing.html", {
        "tiers": _tier_cards(),
        "trial_days": TRIAL_DAYS,
        "is_premium": user.is_authenticated and user.is_premium,
        "current_tier": getattr(user, "tier", ""),
        "trial_available": user.is_authenticated and not getattr(user, "has_used_trial", True)
                           and not getattr(user, "is_guest", True),
    })


@require_POST
@login_required
def subscribe(request):
    user = request.user
    plan_code = request.POST.get("plan", "")
    if user.is_guest:
        messages.error(request, _("Creá una cuenta para suscribirte."))
        return redirect("register")
    if get_plan(plan_code) is None:
        return HttpResponseBadRequest("Plan inválido")

    coupon = None
    code = (request.POST.get("coupon") or "").strip()
    if code:
        coupon = service.validate_coupon(code)
        if coupon is None:
            messages.error(request, _("Cupón inválido o agotado."))
            return redirect("pricing")

    trial = request.POST.get("trial") == "1" and not user.has_used_trial
    if trial:
        user.has_used_trial = True
        user.save(update_fields=["has_used_trial"])

    url = get_provider().create_checkout(
        user, plan_code, request, trial=trial, coupon=coupon
    )
    return redirect(url)


@login_required
def success(request):
    if request.user.is_premium:
        messages.success(request, _("¡Bienvenido a Premium! 👑"))
    else:
        messages.info(request, _("Estamos confirmando tu pago…"))
    return render(request, "billing/success.html", {})


@login_required
def manage(request):
    sub = service.active_subscription(request.user)
    return render(request, "billing/manage.html", {
        "subscription": sub,
        "is_premium": request.user.is_premium,
        "tier": request.user.tier,
        "premium_until": request.user.premium_until,
        "stripe": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
    })


@require_POST
@login_required
def portal(request):
    url = get_provider().portal(request.user, request)
    return redirect(url)


@require_POST
@login_required
def cancel(request):
    get_provider().cancel(request.user)
    messages.info(request, _("Tu suscripción no se renovará. Conservás Premium hasta el fin del período."))
    return redirect("billing_manage")


def gift(request):
    plans = [{"code": c, "price": price_display(p), **p} for c, p in GIFT_PLANS.items()]
    return render(request, "billing/gift.html", {"plans": plans})


@require_POST
@login_required
def gift_buy(request):
    plan_code = request.POST.get("plan", "")
    if request.user.is_guest or plan_code not in GIFT_PLANS:
        return redirect("gift")
    if _is_mock():
        g = service.create_gift(request.user, plan_code)
        return render(request, "billing/gift_created.html", {"gift": g})
    url = get_provider().create_gift_checkout(request.user, plan_code, request)
    return redirect(url)


@require_POST
@login_required
def gift_redeem(request):
    code = request.POST.get("code", "")
    g = service.redeem_gift(request.user, code)
    if g:
        messages.success(request, _("¡Canjeaste %(days)s días de %(tier)s! 👑") % {"days": g.days, "tier": g.tier.capitalize()})
        return redirect("billing_manage")
    messages.error(request, _("Código de regalo inválido o ya usado."))
    return redirect("gift")


@login_required
def metrics(request):
    if not request.user.is_staff:
        return HttpResponse(status=403)
    return render(request, "billing/metrics.html", _compute_metrics())


def _compute_metrics():
    from datetime import timedelta
    from django.utils import timezone
    from accounts.models import User
    from .models import GiftCode, Subscription

    Sub = Subscription
    real_users = User.objects.filter(is_guest=False, is_bot=False)
    total = real_users.count()
    premium = real_users.filter(premium_until__gt=timezone.now()).count()

    active = Sub.objects.filter(status=Sub.ACTIVE)
    mrr = 0.0
    by_tier = {"gold": 0, "diamond": 0}
    for s in active:
        plan = get_plan(s.plan_code)
        if plan and plan.get("interval"):
            monthly = plan["amount"] / (12 if plan["interval"] == "year" else 1)
            mrr += monthly
        by_tier[s.tier] = by_tier.get(s.tier, 0) + 1

    last30 = timezone.now() - timedelta(days=30)
    canceled30 = Sub.objects.filter(status=Sub.CANCELED, updated_at__gte=last30).count()
    churn = round(100 * canceled30 / active.count(), 1) if active.count() else 0.0

    return {
        "total_users": total,
        "premium_users": premium,
        "conversion": round(100 * premium / total, 1) if total else 0.0,
        "active_subs": active.count(),
        "mrr": round(mrr / 100, 2),
        "arr": round(mrr * 12 / 100, 2),
        "by_tier": by_tier,
        "trials": Sub.objects.filter(is_trial=True, status=Sub.ACTIVE).count(),
        "past_due": Sub.objects.filter(status=Sub.PAST_DUE).count(),
        "churn": churn,
        "gifts_redeemed": GiftCode.objects.filter(redeemed_by__isnull=False).count(),
    }


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        return HttpResponse(status=404)
    provider = get_provider()
    try:
        event = provider.construct_event(
            request.body, request.META.get("HTTP_STRIPE_SIGNATURE", "")
        )
    except Exception:
        return HttpResponseBadRequest("Webhook inválido")

    _handle_event(event)
    return HttpResponse(status=200)


def _handle_event(event):
    from accounts.models import User

    etype = event["type"]
    obj = event["data"]["object"]

    if etype in ("checkout.session.completed", "invoice.paid"):
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id") or obj.get("client_reference_id")
        if meta.get("kind") == "gift":
            user = User.objects.filter(pk=user_id).first() if user_id else None
            if user:
                service.create_gift(user, meta.get("gift_plan", ""))
            return
        plan_code = meta.get("plan_code", "gold_monthly")
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if user:
                service.activate(
                    user, plan_code, "stripe",
                    customer_id=obj.get("customer", "") or "",
                    subscription_id=obj.get("subscription", "") or "",
                )
    elif etype == "invoice.payment_failed":
        # Dunning: flag the subscription and nudge the customer to update their
        # payment method. Stripe keeps retrying per its dunning settings.
        from accounts.models import User
        from .emails import send_payment_failed
        from .models import Subscription
        sub_id = obj.get("subscription", "")
        if sub_id:
            Subscription.objects.filter(provider_subscription_id=sub_id).update(
                status=Subscription.PAST_DUE
            )
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id")
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if user:
                send_payment_failed(user)

    elif etype == "customer.subscription.deleted":
        from .models import Subscription
        Subscription.objects.filter(
            provider_subscription_id=obj.get("id", "")
        ).update(status=Subscription.EXPIRED)
