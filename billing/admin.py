from django.contrib import admin

from .models import Coupon, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan_code", "tier", "provider", "status",
                    "is_trial", "current_period_end", "created_at")
    list_filter = ("provider", "status", "tier", "is_trial")
    search_fields = ("user__username", "provider_subscription_id")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "free_days", "active",
                    "times_redeemed", "max_redemptions")
    list_filter = ("active",)
    search_fields = ("code",)
