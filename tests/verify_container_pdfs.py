import hashlib
import sys
from pathlib import Path

import pymupdf
from pypdf import PdfReader


def rendered_hash(path: Path) -> str:
    document = pymupdf.open(path)
    assert len(document) >= 1
    digest = hashlib.sha256()
    for page in document:
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
        assert pixmap.width > 500 and pixmap.height > 700
        digest.update(pixmap.samples)
    return digest.hexdigest()


first, second = map(Path, sys.argv[1:3])
expected_text = {
    "final-report.pdf": ["Synthetischer", "Sicherer", "Testbericht", "Revision", "Gefördert"],
    "attendance-sheet.pdf": ["Synthetischer", "Synthetische", "Person"],
}
for filename, markers in expected_text.items():
    first_pdf = first / filename
    second_pdf = second / filename
    reader = PdfReader(first_pdf)
    if filename == "final-report.pdf":
        assert len(reader.pages) == 1, (
            "Der kompakte synthetische Abschlussbericht muss einseitig sein"
        )
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert reader.metadata is not None
    # Embedded fonts may make PDF text extractors insert spaces inside words.
    compact_text = "".join(text.split())
    missing = [marker for marker in markers if "".join(marker.split()) not in compact_text]
    assert not missing, f"{filename}: Textmarker fehlen: {missing}; extrahiert={text!r}"
    assert rendered_hash(first_pdf) == rendered_hash(second_pdf)
