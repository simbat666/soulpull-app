"""
Soulpull MVP — Main URLs (согласно ТЗ §5.4)

Includes:
- API routes (/api/v1/*)
- TonConnect manifest and icon
- Frontend SPA
"""

import base64
import json
import os

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt


# Base64 encoded minimal TON icon (256x256 indigo circle with S)
TON_ICON_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABhGlDQ1BJQ0MgcHJvZmlsZQAAKJF9
kT1Iw0AcxV9TpSIVBzuIOGSoThZERRy1CkWoEGqFVh1MLv2CJg1Jiouj4Fpw8GOx6uDirKuDqyAI
foC4uTkpukiJ/0sKLWI8OO7Hu3uPu3eA0Kgy1eyZAFTNMlLxmJjNrYrdryigjz6MYFRipp5IL2bg
Ob7u4ePrXZRneZ/7c/QqeZMBPpF4lumGRbxBPL1p6Zz3iUOsJCnE58RjBl2Q+JHrsstvnIsOCzwz
ZGTSmUMsEstFuxfMYqxEPE0cVlSN8oWMyyrnLc5qpcZa9+QvDOW15TXG4YSExBIyODIoowQbYjRo
ppBIUE/RwT/s+EOXTJKrRmFjGlYoI6mkRfVa0/e1Zyc7PKPIZLAANQ+y6JhDFrvUquM4z4Pwbhqf
6tpC7AcA7UZxov0wZCTUsBYF+gG47wyfWAAl0gpQ8c4X2OwsQOE9oBE4+gRPDShBo77B0c3OPA+d
AfqALqlWvgEODoAxAmWve7y7p7O3f88Q7fsF5KZyodP1kHsAAAAGYktHRAD/AP8A/6C9p5MAAAAJ
cEhZcwAALiMAAC4jAXilP3YAAAAHdElNRQfoBgcNLhAzJx9YAAAB/klEQVR42u3BgQAAAADDoPlT
X+AIVQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAmDw7
GAAAAAAAIP/XRhjCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMDsbQQAAAAAAAAQ/X9tRwIAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABg87WAAAAAAAAD6/9peBQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJ+IBlUQDQAAAAAAAElFTkSuQmCC
"""


def tonconnect_manifest(request):
    """
    GET /tonconnect-manifest.json
    Returns TonConnect manifest with Cache-Control: no-store
    """
    origin = request.build_absolute_uri("/").rstrip("/")
    
    manifest = {
        "url": origin,
        "name": "Soulpull",
        "iconUrl": f"{origin}/ton-icon.png",
        "termsOfUseUrl": f"{origin}/terms",
        "privacyPolicyUrl": f"{origin}/privacy",
    }
    
    response = JsonResponse(manifest)
    response["Cache-Control"] = "no-store"
    return response


def ton_icon(request):
    """
    GET /ton-icon.png
    Returns icon from base64
    """
    try:
        # Clean and decode base64
        clean_b64 = "".join(TON_ICON_BASE64.split())
        image_data = base64.b64decode(clean_b64)
        return HttpResponse(image_data, content_type="image/png")
    except Exception:
        # Return minimal 1x1 transparent PNG on error
        minimal_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        return HttpResponse(minimal_png, content_type="image/png")


def index(request):
    """
    SPA entry point - serves frontend/index.html
    """
    from django.shortcuts import render
    return render(request, "index.html")


def terms(request):
    """Terms of Use placeholder"""
    return HttpResponse("<h1>Terms of Use</h1><p>Coming soon.</p>", content_type="text/html")


def privacy(request):
    """Privacy Policy placeholder"""
    return HttpResponse("<h1>Privacy Policy</h1><p>Coming soon.</p>", content_type="text/html")


urlpatterns = [
    # API
    path("api/v1/", include("api.urls")),
    
    # TonConnect
    path("tonconnect-manifest.json", tonconnect_manifest, name="tonconnect_manifest"),
    path("ton-icon.png", ton_icon, name="ton_icon"),
    
    # Legal
    path("terms", terms, name="terms"),
    path("privacy", privacy, name="privacy"),
    
    # SPA
    path("", index, name="index"),
]
