from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


def ready(_request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    response = JsonResponse({"status": "ready"})
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    path("health/", health, name="health"),
    path("ready/", ready, name="ready"),
    path("admin/", admin.site.urls),
    path("auth/", include("werkblatt.identities.urls")),
    path("settings/", include("werkblatt.organizations.urls")),
    path("documentation/", include("werkblatt.documentation.urls")),
    path("documents/", include("werkblatt.documents.urls")),
    path("", include("werkblatt.workshops.urls")),
]
