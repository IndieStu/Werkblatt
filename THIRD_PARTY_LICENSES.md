# Drittkomponenten und Lizenzhinweise

Stand: 24. September 2026
Bezugsstand: `uv.lock` aus Werkblatt-Commit
`4e28a642e2e46df38ad42ffc25d1d7d750d56383`

Diese Übersicht ändert keine Lizenz eines Bestandteils. Maßgeblich bleiben die
mit den jeweiligen Paketen ausgelieferten Lizenz- und Copyrightdateien. Das
Releaseverfahren muss die Liste für jeden neuen Lock- und Containerstand neu
erzeugen und prüfen.

## Direkt verwendete Python-Pakete

| Paket | Verwendung | Lizenz |
|---|---|---|
| Authlib | Runtime | BSD-3-Clause |
| CairoSVG | Runtime | LGPL-3.0-or-later |
| Django | Runtime | BSD-3-Clause |
| Gunicorn | Runtime | MIT |
| HTTPX | Runtime | BSD-3-Clause |
| Pillow | Runtime | MIT-CMU |
| Psycopg / psycopg-binary | Runtime | LGPL-3.0-only |
| Requests | Runtime | Apache-2.0 |
| ReportLab | Runtime | BSD |
| WeasyPrint | Runtime | BSD-3-Clause |
| WhiteNoise / Brotli | Runtime | MIT |
| pip-audit | Entwicklung/CI | Apache-2.0 |
| pypdf | Entwicklung/Tests | BSD-3-Clause |
| PyMuPDF | Entwicklung/Tests | AGPL-3.0 oder kommerzielle Lizenz |
| pytest | Entwicklung/Tests | MIT |
| pytest-django | Entwicklung/Tests | BSD-3-Clause |
| RESPX | Entwicklung/Tests | BSD-3-Clause |
| Ruff | Entwicklung/CI | MIT |
| Hatchling 1.32.4 | Build | MIT |

PyMuPDF wird nicht in das Runtimeimage installiert. Werkblatt verwendet es
ausschließlich als Testwerkzeug. Die offene AGPL-Lizenzspur wird dabei genutzt.

## Transitive Python-Pakete

| Pakete | Lizenz beziehungsweise Lizenzwahl |
|---|---|
| anyio, Brotli, charset-normalizer, filelock, fonttools, h11, markdown-it-py, mdurl, packageurl-python, pip-requirements-parser, platformdirs, pluggy, pyparsing, rich, tinyhtml5, tomli, tomli-w, urllib3 | MIT |
| asgiref, cairocffi, cssselect2, httpcore, idna, joserfc, pycparser, pydyf, sqlparse, tinycss2, webencodings | BSD/BSD-3-Clause |
| boolean.py | BSD-2-Clause |
| CacheControl, cyclonedx-python-lib, license-expression, msgpack, pip-api, py-serializable, sortedcontainers, tzdata, zopfli | Apache-2.0 |
| certifi | MPL-2.0 |
| cffi | MIT-0 |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| defusedxml | PSF-2.0 |
| packaging | Apache-2.0 OR BSD-2-Clause |
| Pygments | BSD-2-Clause |
| pyphen | GPL-2.0+ OR LGPL-2.1+ OR MPL-1.1 |
| typing-extensions | PSF-2.0 |

Pyphen enthält unveränderte Trennwörterbücher aus LibreOffice. Diese können je
nach Wörterbuch unter GPL, LGPL und/oder MPL stehen. Ihre Hinweise bleiben Teil
des installierten Pyphen-Pakets; sie werden nicht unter die Werkblatt-Lizenz
gestellt.

## Schrift und Produktassets

- Inter Regular und SemiBold: SIL Open Font License 1.1; vollständiger Text in
  `licenses/Inter-OFL-1.1.txt`.
- Werkblatt Brand System: nicht als Open-Source-Asset freigegeben; siehe
  `BRAND_POLICY.md`.
- Organisations-, Projekt- und Förderlogos: nicht im Repository enthalten;
  Rechte und Freigaben verantwortet die jeweilige hochladende Organisation.

## Container- und Systembestandteile

Das Runtimeimage basiert auf dem offiziellen, per Multi-Arch-Digest fixierten
Python-Slim-Image und enthält
Debian-Systempakete für GDK Pixbuf, Pango, HarfBuzz und `shared-mime-info`.
Diese Bestandteile bleiben unter ihren jeweiligen MIT-, LGPL-, GPL- und
sonstigen Paketlizenzen. Ihre maschinenlesbare Stückliste wird aus dem
tatsächlich gebauten Image als CycloneDX-SBOM erzeugt. Die zugehörigen
Debian-Copyrightdateien verbleiben im Image unter `/usr/share/doc`.

PostgreSQL läuft als separater, ebenfalls per Digest fixierter Container unter
der PostgreSQL License; sein Image ist kein Bestandteil des
Werkblatt-Programmquellcodes. Die Digests werden bei kontrollierten Updates
gemeinsam mit SBOM, Tests und Third-Party-Inventar erneuert.
