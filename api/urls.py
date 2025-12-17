"""
URL configuration for API v1.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Health check
    path('health', views.health, name='health'),
    
    # Пользовательские endpoints
    path('register', views.register, name='register'),
    path('register-wallet', views.register_wallet, name='register_wallet'),
    path('wallet', views.wallet, name='wallet'),
    path('intent', views.intent, name='intent'),
    path('me', views.me, name='me'),
    path('payout', views.payout, name='payout'),
    path('confirm', views.confirm, name='confirm'),
    path('jetton/wallet', views.jetton_wallet, name='jetton_wallet'),
    
    # Админские endpoints (требуют X-Admin-Token)
    path('payout/mark', views.payout_mark, name='payout_mark'),
]
