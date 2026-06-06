from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import service
from .plans import PLANS, get_plan, price_display
from .providers import get_provider


def pricing(request):
    plans = [
        {"code": code, "price": price_display(p), **p}
        for code, p in PLANS.items()
    ]
    return render(request, "billing/pricing.html", {
        "plans": plans,
        "is_premium": request.user.is_authenticated and request.user.is_premium,
    })


@require_POST
@login_required
def subscribe(request):
    plan_code = request.POST.get("plan", "")
    if request.user.is_guest:
        messages.error(request, "Creá una cuenta para suscribirte.")
        return redirect("register")
    if get_plan(plan_code) is None:
        return HttpResponseBadRequest("Plan inválido")
    url = get_provider().create_checkout(request.user, plan_code, request)
    return redirect(url)


@login_required
def success(request):
    # Mock provider activates synchronously; Stripe activates via webhook, so
    # entitlement may take a moment to appear after returning here.
    if request.user.is_premium:
        messages.success(request, "¡Bienvenido a Premium! 👑")
    else:
        messages.info(request, "Estamos confirmando tu pago…")
    return render(request, "billing/success.html", {})


@login_required
def manage(request):
    sub = service.active_subscription(request.user)
    return render(request, "billing/manage.html", {
        "subscription": sub,
        "is_premium": request.user.is_premium,
        "premium_until": request.user.premium_until,
    })


@require_POST
@login_required
def cancel(request):
    get_provider().cancel(request.user)
    messages.info(request, "Tu suscripción no se renovará. Conservás Premium hasta el fin del período.")
    return redirect("billing_manage")


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
        plan_code = meta.get("plan_code", "monthly")
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if user:
                service.activate(
                    user, plan_code, "stripe",
                    customer_id=obj.get("customer", "") or "",
                    subscription_id=obj.get("subscription", "") or "",
                )
    elif etype == "customer.subscription.deleted":
        sub_id = obj.get("id", "")
        from .models import Subscription
        Subscription.objects.filter(provider_subscription_id=sub_id).update(
            status=Subscription.EXPIRED
        )
