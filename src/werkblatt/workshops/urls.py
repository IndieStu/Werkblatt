from django.urls import path

from . import views

urlpatterns = [
    path("", views.workshop_index, name="workshop-index"),
    path("list/", views.workshop_list, name="workshop-list"),
    path("calendar/", views.workshop_calendar, name="workshop-calendar"),
    path("view/", views.workshop_view_preference, name="workshop-view-preference"),
    path("new/", views.native_workshop_edit, name="workshop-create"),
    path("pretix/new/", views.pretix_workshop_create, name="pretix-workshop-create"),
    path(
        "pretix/creations/<uuid:creation_id>/",
        views.pretix_workshop_review,
        name="pretix-workshop-review",
    ),
    path(
        "pretix/creations/<uuid:creation_id>/publish/",
        views.pretix_workshop_publish,
        name="pretix-workshop-publish",
    ),
    path("<uuid:workshop_id>/edit/", views.native_workshop_edit, name="workshop-edit"),
    path("<uuid:workshop_id>/visibility/", views.workshop_visibility, name="workshop-visibility"),
    path(
        "<uuid:workshop_id>/documentation-requirement/",
        views.workshop_requirement,
        name="workshop-requirement",
    ),
    path("pretix-rules/", views.pretix_rule_list, name="pretix-rule-list"),
    path("pretix-rules/new/", views.pretix_rule_edit, name="pretix-rule-create"),
    path("pretix-rules/<uuid:rule_id>/", views.pretix_rule_edit, name="pretix-rule-edit"),
    path(
        "pretix-creation/",
        views.pretix_creation_settings,
        name="pretix-creation-settings",
    ),
    path(
        "pretix-creation/presets/new/",
        views.pretix_creation_preset_edit,
        name="pretix-creation-preset-create",
    ),
    path(
        "pretix-creation/presets/<uuid:preset_id>/",
        views.pretix_creation_preset_edit,
        name="pretix-creation-preset-edit",
    ),
    path(
        "pretix-creation/presets/<uuid:preset_id>/check/",
        views.pretix_creation_preset_check,
        name="pretix-creation-preset-check",
    ),
    path(
        "pretix-creation/funding-texts/new/",
        views.pretix_funding_text_edit,
        name="pretix-funding-text-create",
    ),
    path(
        "pretix-creation/funding-texts/<uuid:funding_text_id>/",
        views.pretix_funding_text_edit,
        name="pretix-funding-text-edit",
    ),
]
