"""Transactional emails. No-ops when the user has no email address.

In development these print to the console (console email backend); configure
SMTP via env in production.
"""

from django.conf import settings
from django.core.mail import send_mail


def _send(user, subject, body):
    email = getattr(user, "email", "")
    if not email:
        return False
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email],
              fail_silently=True)
    return True


def send_welcome(user):
    return _send(
        user, "¡Bienvenido a Scrabbly! 🎉",
        f"Hola {user.display_name},\n\n"
        "Tu cuenta está lista. Entrá al lobby, jugá una partida rápida o "
        "desafiá a la IA. ¡Que disfrutes!\n\n— El equipo de Scrabbly",
    )


def send_receipt(user, subscription):
    from .plans import get_plan, price_display
    plan = get_plan(subscription.plan_code) or {}
    price = price_display(plan) if plan else ""
    return _send(
        user, "Tu recibo de Scrabbly Premium 👑",
        f"Hola {user.display_name},\n\n"
        f"Gracias por tu suscripción {plan.get('name', subscription.plan_code)} "
        f"({price}).\nTu acceso {subscription.tier.capitalize()} está activo "
        f"hasta {subscription.current_period_end:%d/%m/%Y}.\n\n"
        "Gestioná tu suscripción en /premium/manage/.\n\n— Scrabbly",
    )


def send_payment_failed(user):
    return _send(
        user, "Problema con tu pago de Scrabbly Premium",
        f"Hola {user.display_name},\n\n"
        "No pudimos procesar el cobro de tu suscripción. Reintentaremos en los "
        "próximos días. Actualizá tu método de pago en /premium/manage/ para no "
        "perder tus beneficios Premium.\n\n— Scrabbly",
    )


def send_gift_purchased(user, gift):
    return _send(
        user, "Tu código de regalo Scrabbly 🎁",
        f"Hola {user.display_name},\n\n"
        f"¡Gracias por regalar Premium! Compartí este código:\n\n"
        f"    {gift.code}\n\n"
        f"Quien lo canjee recibirá {gift.days} días de {gift.tier.capitalize()}.\n\n"
        "— Scrabbly",
    )
