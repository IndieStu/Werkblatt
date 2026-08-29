from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import content_disposition_header

from werkblatt.documentation.models import Documentation

from .models import GeneratedDocument, generated_document_filename
from .rendering import render_attendance_sheet


@login_required
def generate_attendance(request: HttpRequest, documentation_id):
    if request.method != "POST":
        raise Http404
    documentation = get_object_or_404(
        Documentation.objects.for_organization(request.organization_context.organization_id),
        pk=documentation_id,
    )
    try:
        document = render_attendance_sheet(documentation, request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("documentation-detail", workshop_id=documentation.workshop_id)
    return redirect("document-download", document_id=document.id)


@login_required
def document_download(request: HttpRequest, document_id):
    document = get_object_or_404(
        GeneratedDocument.objects.for_organization(request.organization_context.organization_id),
        pk=document_id,
    )
    if not document.pdf_file or document.status == GeneratedDocument.Status.RENDER_FAILED:
        raise Http404
    response = FileResponse(document.pdf_file.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        True, generated_document_filename(document)
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
