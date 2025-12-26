from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("register-wallet", views.register_wallet, name="register_wallet"),
    path("me", views.me, name="me"),
    path("ton-proof/payload", views.ton_proof_payload, name="ton_proof_payload"),
    path("ton-proof/verify", views.ton_proof_verify, name="ton_proof_verify"),
]


