from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Identity, Membership, User


@admin.register(User)
class WerkblattUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Werkblatt", {"fields": ("display_name", "preferred_language", "theme")}),
    )


admin.site.register(Identity)
admin.site.register(Membership)
