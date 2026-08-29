import hashlib
import io
import json
from ctypes.util import find_library
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from werkblatt.documentation.models import DocumentationRevision, TemplateOutputDefinition
from werkblatt.identities.models import Membership
from werkblatt.organizations.models import BrandAssetVersion

from .models import GeneratedDocument


def _require_document_access(organization_id, user):
    if (
        not user.is_authenticated
        or not user.memberships.filter(
            organization_id=organization_id, status=Membership.Status.ACTIVE
        ).exists()
    ):
        raise PermissionDenied("Keine Berechtigung für diese Organisation")


def render_html_with_weasyprint(html: str, allowed_uris: set[str]) -> bytes:
    if not find_library("pango-1.0") and not find_library("pango-1.0-0"):
        raise OSError("Pango-Laufzeit nicht verfügbar")
    from weasyprint import HTML, default_url_fetcher

    def restricted_fetcher(url, *args, **kwargs):
        if url not in allowed_uris:
            raise ValueError("PDF-Ressource ist nicht freigegeben")
        return default_url_fetcher(url, *args, **kwargs)

    return HTML(string=html, url_fetcher=restricted_fetcher).write_pdf()


def _get_or_create_generated_document(**kwargs):
    lookup = {key: value for key, value in kwargs.items() if key != "defaults"}
    try:
        with transaction.atomic():
            return GeneratedDocument.objects.get_or_create(**kwargs)
    except IntegrityError:
        return GeneratedDocument.objects.get(**lookup), False


def _claim_render(document: GeneratedDocument) -> bool:
    claimed = GeneratedDocument.objects.filter(
        pk=document.pk,
        status__in=[GeneratedDocument.Status.PENDING, GeneratedDocument.Status.RENDER_FAILED],
    ).update(status=GeneratedDocument.Status.RENDERING)
    document.refresh_from_db()
    return claimed == 1


def _reportlab_pdf(template_name, context):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Werkblatt Workshop-Dokumentation",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Project",
            parent=styles["BodyText"],
            textColor="#006b72",
            fontName="Helvetica-Bold",
        )
    )
    styles.add(ParagraphStyle(name="Stat", parent=styles["BodyText"], alignment=TA_CENTER))
    story = []
    audit_text = ""
    logos = [asset for asset in context.get("assets", []) if asset["zone"] == "header"]
    if logos:
        logo_cells = [
            Image(asset["preview_path"], width=42 * mm, height=16 * mm, kind="proportional")
            for asset in logos
        ]
        story.extend([Table([logo_cells]), Spacer(1, 5 * mm)])
    if template_name.endswith("attendance_sheet.html"):
        template = context["template"]
        workshop = context["workshop"]
        story.extend(
            [
                Paragraph(template.project_title or "Teilnahmeliste", styles["Project"]),
                Paragraph(workshop.title, styles["Title"]),
                Paragraph(
                    f"<b>Datum:</b> {workshop.starts_at:%d.%m.%Y, %H:%M} &nbsp; "
                    f"<b>Ort:</b> {workshop.location}",
                    styles["BodyText"],
                ),
                Spacer(1, 4 * mm),
                Paragraph(template.attendance_text, styles["BodyText"]),
                Spacer(1, 3 * mm),
            ]
        )
        rows = [["Name"] + (["Unterschrift"] if context["output"].include_signature_column else [])]
        rows += [
            [person["display_name"]] + ([""] if context["output"].include_signature_column else [])
            for person in context["participants"]
        ]
        rows += [[""] * len(rows[0]) for _ in context["blank_rows"]]
        table = Table(
            rows,
            colWidths=[105 * mm, 55 * mm] if len(rows[0]) == 2 else [160 * mm],
            rowHeights=[8 * mm] + [12 * mm] * (len(rows) - 1),
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9eacad")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f4")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
    else:
        snapshot = context["snapshot"]
        template = snapshot["template"]
        output_definition = context["output"]
        workshop = context["workshop"]
        story.extend(
            [
                Paragraph(template["project_title"] or "Workshop-Dokumentation", styles["Project"]),
                Paragraph(workshop.title, styles["Title"]),
                Paragraph(
                    f"<b>Datum:</b> {workshop.starts_at:%d.%m.%Y, %H:%M} &nbsp; "
                    f"<b>Ort:</b> {workshop.location}",
                    styles["BodyText"],
                ),
                Spacer(1, 5 * mm),
            ]
        )
        if output_definition["include_statistics"]:
            stats = snapshot["statistics"]
            cells = [
                Paragraph(f"<b>{stats[key]}</b><br/>{label}", styles["Stat"])
                for key, label in [
                    ("registered", "Angemeldet"),
                    ("present_registered", "Anwesend"),
                    ("no_shows", "No-Shows"),
                    ("walk_ins", "Spontan"),
                    ("present_total", "Teilgenommen"),
                ]
            ]
            statistics_table = Table([cells], colWidths=[32 * mm] * 5)
            statistics_table.setStyle(
                TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d3d4"))])
            )
            story.extend([statistics_table, Spacer(1, 5 * mm)])
        if output_definition["include_participant_names"]:
            rows = [["Teilnehmende", "Art"]] + [
                [
                    person["display_name"],
                    "Spontan" if person["origin"] == "walk_in" else "Angemeldet",
                ]
                for person in snapshot["participants"]
                if person["present"]
            ]
            story.extend(
                [
                    Paragraph("Teilnehmende", styles["Heading2"]),
                    Table(
                        rows,
                        colWidths=[110 * mm, 50 * mm],
                        style=[
                            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#ccd5d6")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ],
                    ),
                    Spacer(1, 4 * mm),
                ]
            )
        if output_definition["include_facilitators"]:
            names = ", ".join(person["display_name"] for person in snapshot["facilitators"])
            conducted = "Ja" if snapshot["documentation"]["conducted_as_planned"] else "Nein"
            story.append(
                KeepTogether(
                    [
                        Paragraph("Durchführung", styles["Heading2"]),
                        Paragraph(
                            f"<b>Durchführende:</b> {names}<br/><b>Wie geplant:</b> {conducted}",
                            styles["BodyText"],
                        ),
                    ]
                )
            )
        visible_fields = [
            field
            for field in template["custom_fields"]
            if output_definition["kind"] in field["include_in_output_kinds"]
            and field["value"] is not None
        ]
        if visible_fields:
            field_paragraphs = [
                Paragraph(f"<b>{field['label']}:</b> {field['value']}", styles["BodyText"])
                for field in visible_fields
            ]
            story.extend([Paragraph("Zusatzangaben", styles["Heading2"]), *field_paragraphs])
        if output_definition["include_report"]:
            story.extend(
                [
                    Paragraph("Workshopauswertung", styles["Heading2"]),
                    Paragraph(
                        snapshot["documentation"]["report"] or "Keine Auswertung eingetragen.",
                        styles["BodyText"],
                    ),
                ]
            )
        revision = context["revision"]
        finalization = snapshot["finalization"]
        finalized_at = context.get("finalized_at")
        finalized_display = (
            finalized_at.strftime("%d.%m.%Y um %H:%M Uhr") if finalized_at else "unbekannt"
        )
        audit_text = (
            f"Revision {revision.number} · abgeschlossen am {finalized_display} · "
            f"{finalization['created_by_display_name']}"
        )
    footer_assets = [
        asset
        for asset in context.get("assets", [])
        if asset["zone"] in {"project", "funding_footer"}
    ]
    if footer_assets:
        if any(asset.get("show_funded_by_label") for asset in footer_assets):
            story.extend([Spacer(1, 7 * mm), Paragraph("Gefördert durch", styles["Italic"])])
        story.append(
            Table(
                [
                    [
                        Image(
                            asset["preview_path"],
                            width=42 * mm,
                            height=15 * mm,
                            kind="proportional",
                        )
                        for asset in footer_assets
                    ]
                ]
            )
        )

    def draw_audit_footer(canvas, _document):
        if not audit_text:
            return
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#667477"))
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(17 * mm, 9 * mm, audit_text)
        canvas.restoreState()

    document.build(story, onFirstPage=draw_audit_footer, onLaterPages=draw_audit_footer)
    return output.getvalue()


def _asset_context(organization_id, assets):
    result = []
    for item in assets:
        version = BrandAssetVersion.objects.get(
            organization_id=organization_id,
            pk=item["asset_version_id"],
            sha256=item["sha256"],
        )
        result.append(
            {
                **item,
                "uri": Path(version.original_file.path).as_uri(),
                "preview_path": version.preview_file.path,
            }
        )
    return result


def _render(document, template_name, context):
    try:
        html = render_to_string(template_name, context)
        try:
            allowed_uris = {
                value
                for value in [
                    context.get("font_regular_uri"),
                    context.get("font_semibold_uri"),
                    *(asset.get("uri") for asset in context.get("assets", [])),
                ]
                if value
            }

            pdf = render_html_with_weasyprint(html, allowed_uris)
            renderer_version = "weasyprint-69/v1"
        except (ImportError, OSError):
            pdf = _reportlab_pdf(template_name, context)
            renderer_version = "reportlab-fallback/v1"
        document.pdf_file.save("document.pdf", ContentFile(pdf), save=False)
        document.pdf_sha256 = hashlib.sha256(pdf).hexdigest()
        document.byte_size = len(pdf)
        document.status = GeneratedDocument.Status.RENDERED
        document.renderer_version = renderer_version
        document.attempt_count += 1
        document.last_error_class = ""
        document.save()
    except Exception as exc:
        document.status = GeneratedDocument.Status.RENDER_FAILED
        document.attempt_count += 1
        document.last_error_class = type(exc).__name__
        document.save(update_fields=["status", "attempt_count", "last_error_class", "updated_at"])
        raise
    return document


def render_revision_outputs(revision: DocumentationRevision, user):
    _require_document_access(revision.organization_id, user)
    snapshot = revision.snapshot
    template = snapshot.get("template")
    if not template:
        return []
    assets = _asset_context(revision.organization_id, template["assets"])
    workshop_snapshot = snapshot["workshop"]
    workshop = SimpleNamespace(
        title=workshop_snapshot["title"],
        starts_at=parse_datetime(workshop_snapshot["starts_at"]),
        ends_at=(
            parse_datetime(workshop_snapshot["ends_at"])
            if workshop_snapshot.get("ends_at")
            else None
        ),
        location=workshop_snapshot["location"],
    )
    finalized_at = parse_datetime(snapshot["finalization"]["created_at"])
    if finalized_at and timezone.is_aware(finalized_at):
        finalized_at = timezone.localtime(finalized_at)
    generated = []
    for output in template["outputs"]:
        if output["kind"] == TemplateOutputDefinition.Kind.ATTENDANCE_SHEET:
            continue
        canonical = json.dumps(
            {"snapshot": snapshot, "output": output},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        input_hash = hashlib.sha256(canonical.encode()).hexdigest()
        document, _created = _get_or_create_generated_document(
            organization_id=revision.organization_id,
            workshop_id=revision.documentation.workshop_id,
            revision=revision,
            template_version_id=template["version_id"],
            output_kind=output["kind"],
            input_sha256=input_hash,
            defaults={"output_name": output["display_name"], "created_by": user},
        )
        if _claim_render(document):
            _render(
                document,
                "documents/final_report.html",
                {
                    "snapshot": snapshot,
                    "workshop": workshop,
                    "output": output,
                    "assets": assets,
                    "created_at": timezone.now(),
                    "revision": revision,
                    "finalized_at": finalized_at,
                    "font_regular_uri": Path(
                        settings.BASE_DIR / "static/werkblatt/fonts/Inter-Regular.woff2"
                    ).as_uri(),
                    "font_semibold_uri": Path(
                        settings.BASE_DIR / "static/werkblatt/fonts/Inter-SemiBold.woff2"
                    ).as_uri(),
                },
            )
        generated.append(document)
    return generated


def render_attendance_sheet(documentation, user):
    _require_document_access(documentation.organization_id, user)
    assignment = documentation.template_assignment
    if not assignment:
        raise ValueError("Keine Dokumentvorlage gewählt")
    if not documentation.workshop.location.strip():
        raise ValueError("Für die Teilnahmeliste muss ein Workshoport angegeben werden")
    output = assignment.template_version.outputs.filter(
        kind=TemplateOutputDefinition.Kind.ATTENDANCE_SHEET, enabled=True
    ).first()
    if not output:
        raise ValueError("Diese Vorlage enthält keine Teilnahmeliste")
    participants = [
        {"display_name": entry.display_name}
        for entry in documentation.participants.filter(origin="registered").order_by("display_name")
    ]
    input_data = {
        "workshop_id": str(documentation.workshop_id),
        "version_id": str(assignment.template_version_id),
        "participants": participants,
        "output": output.kind,
    }
    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    document, _created = _get_or_create_generated_document(
        organization_id=documentation.organization_id,
        workshop=documentation.workshop,
        revision=None,
        template_version=assignment.template_version,
        output_kind=output.kind,
        input_sha256=input_hash,
        defaults={"output_name": output.display_name, "created_by": user},
    )
    if _claim_render(document):
        assets = [
            {
                "asset_name": placement.asset_version.asset.display_name,
                "uri": Path(placement.asset_version.original_file.path).as_uri(),
                "preview_path": placement.asset_version.preview_file.path,
                "zone": placement.zone,
                "role": placement.role,
                "show_funded_by_label": placement.show_funded_by_label,
            }
            for placement in assignment.template_version.asset_placements.select_related(
                "asset_version__asset"
            )
        ]
        _render(
            document,
            "documents/attendance_sheet.html",
            {
                "workshop": documentation.workshop,
                "template": assignment.template_version,
                "output": output,
                "participants": participants,
                "blank_rows": range(5),
                "assets": assets,
            },
        )
    return document
