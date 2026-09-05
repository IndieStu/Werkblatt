from django.contrib import admin

from .models import PretixEventRule, Workshop, WorkshopRegistration

admin.site.register(Workshop)
admin.site.register(WorkshopRegistration)
admin.site.register(PretixEventRule)
