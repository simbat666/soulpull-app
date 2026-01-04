"""
Soulpull MVP — API URLs (согласно ТЗ §5)
"""

from django.urls import path
from . import views

urlpatterns = [
    # Health
    path("health", views.health, name="health"),
    
    # Registration & Wallet
    path("register", views.register, name="register"),
    path("wallet", views.wallet, name="wallet"),
    
    # Intent & Participation
    path("intent", views.intent, name="intent"),
    path("confirm", views.confirm, name="confirm"),
    
    # Profile
    path("me", views.me, name="me"),
    
    # Payout
    path("payout", views.payout, name="payout"),
    path("payout/mark", views.payout_mark, name="payout_mark"),
    
    # Jetton wallet & payment (legacy)
    path("jetton/wallet", views.jetton_wallet, name="jetton_wallet"),
    path("payment/intent", views.payment_intent, name="payment_intent"),
    path("payment/build-tx", views.payment_build_tx, name="payment_build_tx"),
    
    # Payment Orders (TonConnect + TonAPI verification)
    path("payments/create", views.payment_create_order, name="payment_create_order"),
    path("payments/<str:order_id>/status", views.payment_order_status, name="payment_order_status"),
    path("payments/confirm", views.payment_manual_confirm, name="payment_manual_confirm"),
    
    # TON Proof
    path("tonproof/payload", views.tonproof_payload, name="tonproof_payload"),
    path("tonproof/verify", views.tonproof_verify, name="tonproof_verify"),
    
    # Admin
    path("admin/participations/pending", views.admin_participations_pending, name="admin_participations_pending"),
    path("admin/payouts/open", views.admin_payouts_open, name="admin_payouts_open"),
]
