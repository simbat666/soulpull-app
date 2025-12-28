import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone


def index(request):
    # In some production deploy setups templates may be missing from the final artifact,
    # which would crash the whole homepage with 500. Keep "/" resilient: if template
    # rendering fails, fall back to an inline HTML that boots the same static app.
    try:
        return render(request, "index.html")
    except Exception:
        html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Soulpull</title>
    <link rel="stylesheet" href="/static/app.css" />
  </head>
  <body>
    <header class="header">
      <div class="brand">Soulpull</div>
      <div id="tonconnect"></div>
    </header>
    <main class="main">
      <h1>TON Connect</h1>
      <div class="card">
        <div class="row"><div class="label">Статус</div><div class="value" id="status">init</div></div>
        <div class="row"><div class="label">Адрес</div><div class="value mono" id="wallet-address"></div></div>
      </div>
    </main>
    <script src="https://unpkg.com/@tonconnect/ui@2.0.0/dist/tonconnect-ui.min.js"></script>
    <script src="/static/app.js"></script>
  </body>
</html>
"""
        return HttpResponse(html, content_type="text/html; charset=utf-8")


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


