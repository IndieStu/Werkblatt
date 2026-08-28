from django.contrib import admin

from .models import Documentation, DocumentationRevision, Facilitator, ParticipantEntry


@admin.register(DocumentationRevision)
class DocumentationRevisionAdmin(admin.ModelAdmin):
    list_display = ["documentation", "number", "created_at", "snapshot_sha256"]
    readonly_fields = [
        "organization",
        "documentation",
        "number",
        "snapshot_schema_version",
        "snapshot",
        "snapshot_sha256",
        "optional_change_reason",
        "created_by",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Documentation)
admin.site.register(ParticipantEntry)
admin.site.register(Facilitator)
