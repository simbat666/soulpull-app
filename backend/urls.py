from django.contrib import admin
from django.urls import path, include

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("tonconnect-manifest.json", views.tonconnect_manifest, name="tonconnect_manifest"),
    path("api/v1/", include("api.urls")),
    path("admin/", admin.site.urls),
]


