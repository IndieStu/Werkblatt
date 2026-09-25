from django.contrib import admin

from .models import (
    PretixEventCreation,
    PretixEventCreationPreset,
    PretixEventRule,
    PretixFundingText,
    Workshop,
    WorkshopRegistration,
)

admin.site.register(Workshop)
admin.site.register(WorkshopRegistration)
admin.site.register(PretixEventRule)
admin.site.register(PretixEventCreationPreset)
admin.site.register(PretixFundingText)
admin.site.register(PretixEventCreation)
