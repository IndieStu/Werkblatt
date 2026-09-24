# Abhängigkeits- und Lizenzpolicy

Werkblatt steht unter `AGPL-3.0-or-later`. Neue oder aktualisierte direkte
Abhängigkeiten werden nicht allein aufgrund automatischer Paketmetadaten
akzeptiert.

Jeder entsprechende Pull Request prüft und dokumentiert:

1. fachliche Notwendigkeit und vorhandene Alternativen;
2. konkrete Version, Upstream und tatsächliche Lizenzdatei;
3. Kompatibilität mit `AGPL-3.0-or-later`;
4. Verwendung zur Laufzeit, beim Build oder ausschließlich in Tests;
5. Weitergabe im Wheel, Source-Archiv oder Container;
6. Notice-, Quellcode-, Austausch- oder Namensnennungspflichten;
7. Änderungen an `uv.lock`, `THIRD_PARTY_LICENSES.md` und den SBOMs.

MIT, MIT-0, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0, PostgreSQL License und
Apache-2.0 können nach Abgleich der Originaldatei regelmäßig freigegeben
werden. Unbekannte, individuelle, nichtkommerzielle, No-Derivatives,
Source-Available-, GPL-, AGPL-, LGPL-, MPL- oder EUPL-Angaben benötigen eine
manuelle Prüfung. Eine manuelle Prüfung bedeutet nicht automatisch Ablehnung.

`tests/test_license_compliance.py` hält die Liste direkter Abhängigkeiten als
bewusste Reviewgrenze fest. Eine neue Dependency lässt CI scheitern, bis ihre
Lizenz geprüft und die Baseline aktualisiert wurde. `pip-audit` erzeugt eine
CycloneDX-Stückliste der Python-Umgebung; Trivy erzeugt zusätzlich eine
CycloneDX-Stückliste des tatsächlich gebauten Images. Releaseartefakte müssen
beide SBOMs, Image-Digest, Werkblatt-Commit und Third-Party-Hinweise enthalten.

Zusätzlich enthält `THIRD_PARTY_LICENSES.md` den SHA-256 der geprüften
`uv.lock`. Der CI-Test schlägt bei jeder Lockdatei-Änderung fehl, bis das
vollständige transitive Inventar erneut geprüft und die Baseline bewusst
aktualisiert wurde. Der Ablauf für Dependency-Updates ist:

```bash
uv sync --frozen --all-extras
uv run --with pip-licenses pip-licenses --with-urls --with-license-file --no-license-path
uv run pip-audit
shasum -a 256 uv.lock
```

Die Ergebnisse werden gegen Paketmetadaten und die tatsächlich ausgelieferten
Lizenzdateien geprüft. Erst danach werden `THIRD_PARTY_LICENSES.md` und dessen
Lock-SHA aktualisiert. Ein bloßes Ersetzen des Hashes ohne diese inhaltliche
Prüfung erfüllt die Policy nicht.

Automatische Werkzeuge dürfen keine fremden Copyright-Header überschreiben,
keine Lizenztexte ersetzen und vorbehaltene Brand-Assets nicht pauschal als
AGPL kennzeichnen.
