from django.urls import path

from . import views

urlpatterns = [
    path(
        "documentation/<uuid:documentation_id>/attendance/",
        views.generate_attendance,
        name="generate-attendance",
    ),
    path("<uuid:document_id>/download/", views.document_download, name="document-download"),
]
