from typing import Optional

from django.conf import settings
from django.http import JsonResponse

from api.auth_tokens import parse_bearer_token, verify_token
from api.models import UserProfile


def get_user_from_request(request) -> Optional[UserProfile]:
    token = parse_bearer_token(request.headers.get("Authorization"))
    claims = verify_token(secret=str(getattr(settings, "SECRET_KEY", "")), token=token or "")
    if not claims:
        return None
    return UserProfile.objects.filter(wallet_address=claims.wallet_address).first()


def require_user_or_401(request):
    """
    Convenience helper for views.
    Returns UserProfile or JsonResponse(401).
    """
    user = get_user_from_request(request)
    if not user:
        return JsonResponse({"error": "unauthorized"}, status=401)
    return user


