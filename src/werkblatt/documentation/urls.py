from django.urls import path

from . import template_views
from .views import documentation_detail

urlpatterns = [
    path("workshops/<uuid:workshop_id>/", documentation_detail, name="documentation-detail"),
    path("templates/", template_views.template_list, name="template-list"),
    path("templates/new/", template_views.template_create, name="template-create"),
    path("templates/<uuid:template_id>/", template_views.template_edit, name="template-edit"),
    path(
        "templates/<uuid:template_id>/duplicate/",
        template_views.template_duplicate,
        name="template-duplicate",
    ),
]
