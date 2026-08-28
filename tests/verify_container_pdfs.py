import hashlib
import sys
from pathlib import Path

import fitz
from pypdf import PdfReader


def rendered_hash(path: Path) -> str:
    document = fitz.open(path)
    assert len(document) >= 1
    digest = hashlib.sha256()
    for page in document:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        assert pixmap.width > 500 and pixmap.height > 700
        digest.update(pixmap.samples)
    return digest.hexdigest()


first, second = map(Path, sys.argv[1:3])
expected_text = {
    "final-report.pdf": ["Synthetischer Sicherheitsworkshop", "Sicherer Testbericht"],
    "attendance-sheet.pdf": ["Synthetischer Sicherheitsworkshop", "Synthetische Person"],
}
for filename, markers in expected_text.items():
    first_pdf = first / filename
    second_pdf = second / filename
    reader = PdfReader(first_pdf)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert reader.metadata is not None
    assert all(marker in text for marker in markers)
    assert rendered_hash(first_pdf) == rendered_hash(second_pdf)
