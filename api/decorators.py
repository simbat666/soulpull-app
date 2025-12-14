"""
Декораторы для API.
"""
from functools import wraps
from django.conf import settings
from django.http import JsonResponse


def admin_token_required(view_func):
    """
    Декоратор для проверки заголовка X-Admin-Token.
    Сравнивает значение из заголовка с X_ADMIN_TOKEN из settings.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        admin_token = request.headers.get('X-Admin-Token', '')
        expected_token = settings.X_ADMIN_TOKEN

        if not expected_token:
            return JsonResponse(
                {'error': 'Admin token not configured'},
                status=500
            )

        if admin_token != expected_token:
            return JsonResponse(
                {'error': 'Invalid or missing X-Admin-Token'},
                status=403
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view



