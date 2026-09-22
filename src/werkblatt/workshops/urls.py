from django.urls import path

from . import views

urlpatterns = [
    path("", views.workshop_list, name="workshop-list"),
    path("<uuid:workshop_id>/visibility/", views.workshop_visibility, name="workshop-visibility"),
    path(
        "<uuid:workshop_id>/documentation-requirement/",
        views.workshop_requirement,
        name="workshop-requirement",
    ),
    path("pretix-rules/", views.pretix_rule_list, name="pretix-rule-list"),
    path("pretix-rules/new/", views.pretix_rule_edit, name="pretix-rule-create"),
    path("pretix-rules/<uuid:rule_id>/", views.pretix_rule_edit, name="pretix-rule-edit"),
]
