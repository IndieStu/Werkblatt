from django.urls import path

from . import views

urlpatterns = [
    path("", views.settings_home, name="settings-home"),
    path("organization/", views.organization_profile, name="organization-profile"),
    path("assets/", views.asset_list, name="asset-list"),
    path("assets/new/", views.asset_create, name="asset-create"),
    path("assets/<uuid:asset_id>/", views.asset_edit, name="asset-edit"),
    path("assets/versions/<uuid:version_id>/preview/", views.asset_preview, name="asset-preview"),
]
