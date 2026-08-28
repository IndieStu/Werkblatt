from django.urls import path

from .views import documentation_detail

urlpatterns = [
    path("workshops/<uuid:workshop_id>/", documentation_detail, name="documentation-detail"),
]
