"""
Soulpull MVP — Django Admin Configuration
"""

from django.contrib import admin

from .models import (
    AuthorCode,
    IdempotencyKey,
    Participation,
    ParticipationStatus,
    PayoutRequest,
    RiskEvent,
    TonProofPayload,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "wallet",
        "points",
        "created_at",
    )
    search_fields = ("telegram_id", "username", "wallet")
    list_filter = ("created_at",)


@admin.register(AuthorCode)
class AuthorCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "owner", "created_at")
    search_fields = ("code", "owner__telegram_id")


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "referrer", "status", "tx_hash", "created_at", "confirmed_at")
    search_fields = ("tx_hash", "user__telegram_id", "referrer__telegram_id")
    list_filter = ("status",)
    
    actions = ["confirm_selected", "reject_selected"]
    
    @admin.action(description="Confirm selected participations")
    def confirm_selected(self, request, queryset):
        queryset.update(status=ParticipationStatus.CONFIRMED)
    
    @admin.action(description="Reject selected participations")
    def reject_selected(self, request, queryset):
        queryset.update(status=ParticipationStatus.REJECTED)


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "tx_hash", "created_at")
    search_fields = ("user__telegram_id", "tx_hash")
    list_filter = ("status",)


@admin.register(RiskEvent)
class RiskEventAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "user", "created_at")
    search_fields = ("kind", "user__telegram_id")
    list_filter = ("kind",)


@admin.register(TonProofPayload)
class TonProofPayloadAdmin(admin.ModelAdmin):
    list_display = ("payload", "expires_at", "used_at", "created_at")
    search_fields = ("payload",)
    list_filter = ("used_at",)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "created_at")
    search_fields = ("key",)
