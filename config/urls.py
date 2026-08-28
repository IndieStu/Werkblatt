from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("auth/", include("werkblatt.identities.urls")),
    path("", include("werkblatt.workshops.urls")),
]
