from django.contrib import admin

from .models import AuthorCode, EventLog, Participation, Payment, PayoutRequest, TonProofPayload, UserProfile


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


@admin.register(AuthorCode)
class AuthorCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "owner", "active", "created_at")
    search_fields = ("code", "owner__wallet_address")
    list_filter = ("active",)


@admin.action(description="Confirm selected participations")
def confirm_participations(modeladmin, request, queryset):
    queryset.update(status="CONFIRMED")


@admin.action(description="Reject selected participations")
def reject_participations(modeladmin, request, queryset):
    queryset.update(status="REJECTED")


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount_usd_cents", "status", "tx_hash", "created_at", "confirmed_at")
    search_fields = ("tx_hash", "user__wallet_address")
    list_filter = ("status",)
    actions = [confirm_participations, reject_participations]


