from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("register-wallet", views.register_wallet, name="register_wallet"),
    path("me", views.me, name="me"),
]


