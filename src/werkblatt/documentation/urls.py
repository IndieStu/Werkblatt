from django.urls import path

from . import template_views
from .views import documentation_detail, statistics_csv, statistics_dashboard

urlpatterns = [
    path("statistics/", statistics_dashboard, name="statistics-dashboard"),
    path("statistics/export.csv", statistics_csv, name="statistics-csv"),
    path("workshops/<uuid:workshop_id>/", documentation_detail, name="documentation-detail"),
    path("templates/", template_views.template_list, name="template-list"),
    path("templates/new/", template_views.template_create, name="template-create"),
    path("templates/<uuid:template_id>/", template_views.template_edit, name="template-edit"),
    path(
        "templates/<uuid:template_id>/duplicate/",
        template_views.template_duplicate,
        name="template-duplicate",
    ),
    path(
        "templates/<uuid:template_id>/archive/",
        template_views.template_archive,
        name="template-archive",
    ),
]
