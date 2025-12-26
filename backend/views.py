import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone


def index(request):
    return render(request, "index.html")


def tonconnect_manifest(request):
    """
    Serve JSON from root `tonconnect-manifest.json` (NOT via static).
    """
    manifest_path: Path = settings.BASE_DIR / "tonconnect-manifest.json"  # type: ignore[attr-defined]
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return JsonResponse(data)
    except FileNotFoundError:
        return JsonResponse({"error": "manifest not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "manifest invalid json"}, status=500)


def _now_iso():
    return timezone.now().isoformat()


