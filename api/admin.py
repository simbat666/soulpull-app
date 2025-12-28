from django.contrib import admin

from .models import EventLog, Payment, PayoutRequest, TonProofPayload, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "wallet_address",
        "telegram_id",
        "telegram_username",
        "participation_status",
        "invited_count",
        "paid_count",
        "points",
        "created_at",
        "updated_at",
    )
    search_fields = ("wallet_address", "telegram_username", "telegram_id")
    list_filter = ("participation_status",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount_usd_cents", "amount_nanotons", "status", "tx_hash", "created_at")
    search_fields = ("tx_hash", "comment", "user__wallet_address")
    list_filter = ("status",)


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount_points", "status", "created_at", "updated_at")
    search_fields = ("user__wallet_address",)
    list_filter = ("status",)


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "user", "created_at")
    search_fields = ("event_type", "user__wallet_address")
    list_filter = ("event_type",)


@admin.register(TonProofPayload)
class TonProofPayloadAdmin(admin.ModelAdmin):
    list_display = ("payload", "expires_at", "used_at", "created_at")
    search_fields = ("payload",)
    list_filter = ("used_at",)


