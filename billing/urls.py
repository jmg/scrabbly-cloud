from django.urls import path

from . import views

urlpatterns = [
    path("premium/", views.pricing, name="pricing"),
    path("premium/subscribe/", views.subscribe, name="billing_subscribe"),
    path("premium/success/", views.success, name="billing_success"),
    path("premium/manage/", views.manage, name="billing_manage"),
    path("premium/portal/", views.portal, name="billing_portal"),
    path("premium/cancel/", views.cancel, name="billing_cancel"),
    path("premium/gift/", views.gift, name="gift"),
    path("premium/gift/buy/", views.gift_buy, name="gift_buy"),
    path("premium/gift/redeem/", views.gift_redeem, name="gift_redeem"),
    path("premium/metrics/", views.metrics, name="billing_metrics"),
    path("billing/stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
