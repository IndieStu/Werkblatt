# Lizenz- und Rechteentscheidung

Stand: 24. September 2026
Geprüfter Produktstand: `4e28a642e2e46df38ad42ffc25d1d7d750d56383`

## Entscheidung

Der Werkblatt-Programmcode wird unter `AGPL-3.0-or-later` veröffentlicht. Timo
Hecken hat bestätigt, dass die erforderliche Berechtigung gegenüber Zircula
e.V. vorliegt. Zircula e.V. bleibt Erstanwender und enger
Entwicklungspartner, ist dadurch aber nicht automatisch Rechteinhaber des
gesamten Projekts.

Das Werkblatt Brand System wird nicht freigegeben. Alle Rechte an Name, Logos,
Signet, Claim-Lockups, Icons, Brand-Tokens und Login-Hintergrund bleiben Timo
Hecken vorbehalten. Die verbindliche Pfad- und Nutzungsabgrenzung steht in
`BRAND_POLICY.md`.

## Ergebnis des Kompatibilitätsaudits

Geprüft wurden Git-Historie, Quellcode, Templates, statische Assets,
`pyproject.toml`, `uv.lock`, Buildsystem, Dockerfile, Compose und CI. Es wurden
keine fremden Codekopien, vendorten Bibliotheken, abweichenden Dateiheader oder
Lizenzbedingungen gefunden, die `AGPL-3.0-or-later` für den Werkblatt-Code
verhindern.

Die Runtime-Abhängigkeiten verwenden permissive Lizenzen, LGPL oder MPL. Diese
sind in der vorliegenden Einbindungs- und Distributionsform mit AGPLv3
vereinbar, behalten aber ihre eigenen Notice- und Lizenzpflichten. PyMuPDF ist
ein ausschließlich in Entwicklung und Tests eingesetztes AGPL-Werkzeug und
wird nicht im Runtimeimage installiert. Inter bleibt unter OFL-1.1. Details
stehen in `THIRD_PARTY_LICENSES.md`.

## Release- und Betriebspflichten

- Der unveränderte AGPLv3-Text, `NOTICE.md`, `BRAND_POLICY.md`, die Inter-OFL
  und die Third-Party-Übersicht werden mit Source- und Containerdistributionen
  ausgeliefert.
- Der tatsächlich gebaute Quellstand wird über Buildversion, genaue Source-URL
  und OCI-Labels kenntlich gemacht.
- Nutzende einer modifizierten, über ein Netzwerk angebotenen Version erhalten
  eine deutlich erreichbare Möglichkeit, den korrespondierenden Quellcode
  dieser Version kostenlos abzurufen.
- Python- und Container-SBOM werden für den konkreten Build erzeugt.
- Basisimages sind per Multi-Arch-Digest fixiert und werden nur gemeinsam mit
  Tests, Vulnerability-Scan und Lizenzinventar aktualisiert.
- Neue direkte Abhängigkeiten müssen die Prüfung in
  `docs/dependency-policy.md` durchlaufen.
- Organisations-, Projekt- und Förderlogos sind Laufzeitdaten und niemals Teil
  der Werkblatt-Softwarelizenz.

Dieses technische Lizenz- und Rechteaudit dokumentiert die Projektentscheidung;
es ersetzt keine Rechtsberatung für unbekannte künftige Beiträge oder neue
Abhängigkeiten.
