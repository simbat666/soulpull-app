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

        # CSP - allow TonConnect UI from CDN and all required endpoints
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://telegram.org",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: https: blob:",
            "connect-src 'self' https: wss:",  # Allow all HTTPS/WSS for TonConnect bridges
            "frame-src 'self' https://t.me https://telegram.org",
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

