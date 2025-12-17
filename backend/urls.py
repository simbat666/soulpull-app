"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
import os

# Простая функция для отдачи index.html
def index_view(request):
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        return HttpResponse(f.read(), content_type='text/html')

# Endpoint для TON Connect manifest
@require_http_methods(["GET", "OPTIONS"])
def tonconnect_manifest(request):
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tonconnect-manifest.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            import json
            manifest_data = json.load(f)
            response = JsonResponse(manifest_data)
            response["Access-Control-Allow-Origin"] = "*"
            return response
    except FileNotFoundError:
        return JsonResponse({'error': 'Manifest not found'}, status=404)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('tonconnect-manifest.json', tonconnect_manifest, name='tonconnect_manifest'),
    path('', index_view, name='index'),
]



