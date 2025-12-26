import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone


def _static_url_join(path: str) -> str:
    base = getattr(settings, "STATIC_URL", "/static/") or "/static/"
    base = base if base.endswith("/") else base + "/"
    return base + path.lstrip("/")


def _vite_assets():
    """
    Load Vite build manifest (if present) to inject correct hashed asset names.
    """
    base_dir: Path = settings.BASE_DIR  # type: ignore[attr-defined]
    candidates = [
        base_dir / "frontend" / "dist" / "manifest.json",
        base_dir / "frontend" / "dist" / ".vite" / "manifest.json",
    ]
    manifest_path = next((p for p in candidates if p.exists()), None)
    if not manifest_path:
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    entry = manifest.get("src/main.tsx") or manifest.get("src/main.ts") or manifest.get("index.html")
    if not isinstance(entry, dict):
        return None

    js_file = entry.get("file")
    css_files = entry.get("css") or []
    if not js_file:
        return None

    return {
        "js": _static_url_join(str(js_file)),
        "css": [_static_url_join(str(x)) for x in css_files],
    }


def index(request):
    return render(request, "index.html", {"vite": _vite_assets()})


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


