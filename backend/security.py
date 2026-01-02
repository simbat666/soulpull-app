"""
Soulpull MVP — Security Middleware (согласно ТЗ §9)

Headers:
- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy
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

        # CSP - allow TonConnect UI from CDN
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: https: blob:",
            "connect-src 'self' https://bridge.tonapi.io https://tonapi.io wss://bridge.tonapi.io https://toncenter.com",
            "frame-src 'self' https://t.me",
            "worker-src 'self' blob:",
        ]
        response["Content-Security-Policy"] = "; ".join(csp_parts)

        # Other security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HTTPS redirect hint (actual redirect handled by proxy)
        if not os.getenv("DEBUG"):
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

