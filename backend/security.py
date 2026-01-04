"""
Soulpull MVP — Security Middleware (согласно ТЗ §9)

Headers:
- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy

TonConnect требует доступ к:
- bridge.tonapi.io (HTTP Bridge)
- tonapi.io (TON API)
- connect.tonhubapi.com (Tonhub Bridge)
- tonconnectbridge.mytonwallet.org (MyTonWallet Bridge)
- Разные wallet apps для иконок
"""

import os


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # CSP - МАКСИМАЛЬНО разрешающий для TonConnect
        # TonConnect использует несколько bridge серверов и загружает иконки кошельков
        csp_parts = [
            "default-src 'self'",
            # Scripts: CDN библиотеки + inline для Telegram WebApp
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://telegram.org",
            # Styles: fonts + inline стили от TonConnect UI
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com https://cdn.jsdelivr.net",
            # Fonts
            "font-src 'self' https://fonts.gstatic.com data:",
            # Images: иконки кошельков могут быть откуда угодно
            "img-src 'self' data: blob: https: http:",
            # Connect: ВСЕ HTTPS/WSS для TonConnect bridges и wallets API
            "connect-src 'self' https: wss: http:",
            # Frames: Telegram
            "frame-src 'self' https://t.me https://telegram.org https:",
            # Workers
            "worker-src 'self' blob:",
            # Object (для SVG и т.д.)
            "object-src 'none'",
            # Base URI
            "base-uri 'self'",
        ]
        response["Content-Security-Policy"] = "; ".join(csp_parts)

        # Разрешаем загрузку в iframe из Telegram
        # ВАЖНО: не DENY, а SAMEORIGIN или ALLOW-FROM для Telegram
        response["X-Frame-Options"] = "SAMEORIGIN"
        
        # Другие security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HTTPS redirect hint (actual redirect handled by proxy)
        if not os.getenv("DEBUG"):
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

