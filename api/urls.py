from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("register-wallet", views.register_wallet, name="register_wallet"),
    path("tonproof/payload", views.tonproof_payload, name="tonproof_payload"),
    path("tonproof/verify", views.tonproof_verify, name="tonproof_verify"),
    path("me", views.me, name="me"),
]


