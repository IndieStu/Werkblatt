from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Identity, Membership, User

admin.site.register(User, UserAdmin)
admin.site.register(Identity)
admin.site.register(Membership)
