from django.contrib import admin

from .models import GeneratedDocument


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ("workshop", "output_kind", "status", "created_at")
    readonly_fields = ("pdf_sha256", "input_sha256", "storage_key")
