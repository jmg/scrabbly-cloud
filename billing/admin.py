from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan_code", "provider", "status",
                    "current_period_end", "created_at")
    list_filter = ("provider", "status", "plan_code")
    search_fields = ("user__username", "provider_subscription_id")
