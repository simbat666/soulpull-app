from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("debug-login", views.debug_login, name="debug_login"),
    path("register-wallet", views.register_wallet, name="register_wallet"),
    path("tonproof/payload", views.tonproof_payload, name="tonproof_payload"),
    path("tonproof/verify", views.tonproof_verify, name="tonproof_verify"),
    path("me", views.me, name="me"),
    path("telegram/verify", views.telegram_verify, name="telegram_verify"),
    path("inviter/apply", views.inviter_apply, name="inviter_apply"),
    path("author-code/apply", views.author_code_apply, name="author_code_apply"),
    path("intent", views.intent, name="intent"),
    path("payments/create", views.payments_create, name="payments_create"),
    path("payments/confirm", views.payments_confirm, name="payments_confirm"),
    path("participation/create", views.participation_create, name="participation_create"),
    path("participation/confirm", views.participation_confirm, name="participation_confirm"),
    path("payout/request", views.payout_request, name="payout_request"),
    path("payout/me", views.payout_me, name="payout_me"),
    path("payout/mark", views.payout_mark, name="payout_mark"),
    path("jetton/wallet", views.jetton_wallet, name="jetton_wallet"),
    path("admin/participations/pending", views.admin_participations_pending, name="admin_participations_pending"),
    path("admin/payouts/open", views.admin_payouts_open, name="admin_payouts_open"),
    path("referrals/l1", views.referrals_l1, name="referrals_l1"),
]


