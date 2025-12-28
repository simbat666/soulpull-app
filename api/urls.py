from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("register-wallet", views.register_wallet, name="register_wallet"),
    path("tonproof/payload", views.tonproof_payload, name="tonproof_payload"),
    path("tonproof/verify", views.tonproof_verify, name="tonproof_verify"),
    path("me", views.me, name="me"),
    path("telegram/verify", views.telegram_verify, name="telegram_verify"),
    path("inviter/apply", views.inviter_apply, name="inviter_apply"),
    path("author-code/apply", views.author_code_apply, name="author_code_apply"),
    path("payments/create", views.payments_create, name="payments_create"),
    path("payments/confirm", views.payments_confirm, name="payments_confirm"),
]


