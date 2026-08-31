from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from werkblatt.documents.rendering import render_html_with_weasyprint


class Command(BaseCommand):
    help = "Erzeugt zwei synthetische PDFs mit dem produktiven WeasyPrint-Renderer."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        synthetic_logo_uri = Path(
            settings.BASE_DIR / "static/werkblatt/brand/werkblatt-logo.svg"
        ).as_uri()
        workshop = SimpleNamespace(
            title="Synthetischer Sicherheitsworkshop",
            starts_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
            location="Testort",
        )
        output = {
            "kind": "final_report",
            "include_statistics": True,
            "include_participant_names": True,
            "include_facilitators": True,
            "include_report": True,
        }
        snapshot = {
            "workshop": {"title": workshop.title},
            "documentation": {"conducted_as_planned": True, "report": "Sicherer Testbericht"},
            "statistics": {
                "registered": 1,
                "present_registered": 1,
                "no_shows": 0,
                "walk_ins": 0,
                "present_total": 1,
            },
            "participants": [
                {"display_name": "Synthetische Person", "origin": "registered", "present": True}
            ],
            "facilitators": [{"display_name": "Synthetische Leitung"}],
            "template": {
                "project_title": "Synthetisches Projekt",
                "subtitle": "Renderer-Gate",
                "funding_text": "Gefördert durch ein synthetisches Testprogramm",
                "custom_fields": [],
            },
            "finalization": {
                "created_at": "2026-08-28T10:00:00+00:00",
                "created_by_display_name": "CI",
            },
        }
        final_html = render_to_string(
            "documents/final_report.html",
            {
                "snapshot": snapshot,
                "workshop": workshop,
                "output": output,
                "assets": [
                    {
                        "zone": "funding_footer",
                        "uri": synthetic_logo_uri,
                        "asset_name": "Synthetisches Förderlogo",
                        "show_funded_by_label": True,
                    }
                ],
                "revision": SimpleNamespace(number=1),
                "finalized_at": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
            },
        )
        attendance_html = render_to_string(
            "documents/attendance_sheet.html",
            {
                "workshop": workshop,
                "template": SimpleNamespace(
                    project_title="Synthetisches Projekt",
                    attendance_text="Teilnahme wird bestätigt.",
                    funding_text="",
                ),
                "output": SimpleNamespace(include_signature_column=True),
                "participants": [{"display_name": "Synthetische Person"}],
                "blank_rows": range(2),
                "assets": [],
            },
        )
        for filename, html, allowed_uris in [
            ("final-report.pdf", final_html, {synthetic_logo_uri}),
            ("attendance-sheet.pdf", attendance_html, set()),
        ]:
            pdf = render_html_with_weasyprint(html, allowed_uris)
            if not pdf.startswith(b"%PDF-") or len(pdf) < 1_000:
                raise RuntimeError(f"Ungültige WeasyPrint-Ausgabe: {filename}")
            (output_dir / filename).write_bytes(pdf)
        self.stdout.write(self.style.SUCCESS("WeasyPrint-Produktionsprüfung bestanden."))
