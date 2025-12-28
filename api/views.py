import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import UserProfile


@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "host": request.get_host(),
            "debug": bool(settings.DEBUG),
            "time": timezone.now().isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def register_wallet(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    wallet_address = (payload.get("wallet_address") or "").strip()
    if not wallet_address:
        return JsonResponse({"error": "wallet_address is required"}, status=400)

    obj, created = UserProfile.objects.get_or_create(wallet_address=wallet_address)
    if not created:
        # Touch updated_at
        obj.save(update_fields=["updated_at"])

    return JsonResponse(
        {"success": True, "created": created, "wallet_address": obj.wallet_address},
        status=201 if created else 200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def me(request):
    wallet_address = (request.GET.get("wallet_address") or "").strip()
    if not wallet_address:
        return JsonResponse({"error": "wallet_address query param is required"}, status=400)

    obj = UserProfile.objects.filter(wallet_address=wallet_address).first()
    if not obj:
        return JsonResponse({"error": "user not found"}, status=404)

    return JsonResponse(
        {
            "wallet_address": obj.wallet_address,
            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        }
    )


