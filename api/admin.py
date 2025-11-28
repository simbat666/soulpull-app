from django.contrib import admin
from .models import UserProfile, AuthorCode, Participation, PayoutRequest, RiskEvent


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'wallet_address', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('telegram_id', 'wallet_address')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuthorCode)
class AuthorCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_active', 'created_at', 'expires_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('code',)


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('user', 'tx_hash', 'amount', 'status', 'created_at', 'confirmed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('tx_hash', 'user__telegram_id')
    readonly_fields = ('created_at', 'confirmed_at')


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'wallet_address', 'created_at', 'processed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__telegram_id', 'wallet_address')
    readonly_fields = ('created_at', 'processed_at')
    fields = ('user', 'amount', 'status', 'wallet_address', 'admin_notes', 'created_at', 'processed_at')


@admin.register(RiskEvent)
class RiskEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'participation', 'severity', 'resolved', 'created_at')
    list_filter = ('event_type', 'resolved', 'created_at', 'severity')
    search_fields = ('user__telegram_id', 'description')
    readonly_fields = ('created_at',)
