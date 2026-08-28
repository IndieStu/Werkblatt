# Werkblatt - Phase 0: Architekturentscheidung

Status: freigegeben mit eingearbeiteten Architekturpräzisierungen  
Stand: 28. August 2026  
Produkt: Werkblatt - Workshops einfach dokumentieren.  
Scope: ausschließlich Phase 0; noch keine Feature-Implementierung

## 1. Kurzentscheidung

Werkblatt wird als modularer Monolith auf Basis von Django 5.2 LTS und PostgreSQL 17 geplant. Die Benutzeroberfläche wird serverseitig gerendert und nur dort mit HTMX und kleinem, lokalem JavaScript ergänzt, wo Interaktion ohne vollständigen Seitenwechsel sinnvoll ist. Es gibt in V1 genau einen Webprozess und eine Datenbank; ein separater Worker oder Redis wird erst ergänzt, wenn reale Last oder betrieblich notwendige Hintergrundjobs dies rechtfertigen.

Die fachliche Trennung erfolgt innerhalb einer Anwendung: Identität, Organisationen, Workshops, Dokumentationen, Projekte/Logos und Integrationen sind klar abgegrenzte Module. Pretix, OIDC, WebDAV und PDF-Erzeugung werden über kleine Ports/Adapter gekapselt. Das hält V1 klein, ohne die Kernlogik an eine bestimmte Organisation oder einen externen Dienst zu binden.

Die zentrale Sicherheitsregel lautet: Jeder organisationsbezogene Zugriff beginnt mit einem serverseitig ermittelten `organization_id`-Kontext. Mandantendaten werden nie über ungefilterte globale QuerySets geladen. IDs aus URLs oder Requests bestimmen nicht den Tenant.

## 2. Technologie-Stack

### Fest vorgeschlagen

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | Python 3.13 | Gute Wartbarkeit, starke Django-/PDF-/Integrationsbibliotheken, verständlich für externe Contributors. |
| Webframework | Django 5.2 LTS, jeweils aktueller Patchstand | Bewährter modularer Monolith mit ORM, Migrationen, Sessions, CSRF, sicherem Passwort-Hashing, Admin und Testwerkzeugen. Die LTS-Reihe wird bis April 2028 unterstützt. |
| UI | Django Templates + HTMX, wenig eigenes JavaScript | Der Hauptworkflow ist formular- und listenorientiert. Kein SPA-State, keine doppelte API-/Frontend-Validierung, kleiner Build- und Wartungsaufwand. |
| Styling | eigenes CSS mit Design-Tokens; optional kleine Build-Pipeline für Minifizierung | Das verbindliche Brand-System wird präzise abgebildet, ohne eine fremde Komponentenästhetik einzuschleppen. |
| Datenbank | PostgreSQL 17, aktueller Minor-Release | Reife Constraints, Transaktionen, JSON nur dort, wo Varianten es rechtfertigen, fünfjährige Upstream-Unterstützung bis November 2029. |
| OIDC | standardskonformer Authorization-Code-Flow mit PKCE über eine etablierte Django-kompatible Bibliothek | Kein Authentik-Sonderweg; Authentik, Keycloak oder andere Provider bleiben austauschbar. Die konkrete Bibliothek wird in Phase 1 nach einem kurzen Security-/Maintenance-Spike fixiert. |
| HTTP-Client | `httpx` mit zentraler Timeout-, Redirect- und Transportkonfiguration | Gemeinsame sichere Basis für Pretix und WebDAV; gut testbar über Mock-Transport. |
| PDF | HTML/CSS-Templates + WeasyPrint, Version exakt gepinnt | A4, Seitenumbrüche, eingebettete Fonts und Vektor-SVGs sind gut abbildbar. WeasyPrint weist selbst darauf hin, dass Major-Releases das Rendering ändern können; deshalb visuelle Golden-Master-Tests vor Updates. |
| WebDAV | kleiner eigener Adapter auf einem etablierten HTTP/WebDAV-Client | Die fachliche Storage-Schnittstelle bleibt unabhängig von Nextcloud. Kein Nextcloud-internes API. |
| App-Server | Gunicorn hinter Reverse Proxy | Einfacher, etablierter WSGI-Betrieb. TLS und Request-Limits liegen am Reverse Proxy; Django setzt die Anwendungsregeln durch. |
| Packaging | `pyproject.toml` + reproduzierbarer Lockfile-Workflow | Eine Abhängigkeitsquelle, nachvollziehbare Updates und Container-Builds. Das konkrete Lock-Tool wird in Phase 1 festgelegt. |
| Qualität | Ruff, mypy schrittweise, pytest/pytest-django, Playwright für wenige Kernflüsse | Schnelle Rückmeldung, statische Checks und echte Browserprüfung ohne übergroße E2E-Suite. |
| Deployment | Multi-Stage-Dockerfile + Docker Compose | Einfache lokale Entwicklung und Self-Hosting; Produktionsimage enthält nur Laufzeitabhängigkeiten. |

Offizielle Referenzen: [Django 5.2 LTS](https://www.djangoproject.com/download/), [PostgreSQL-Versionierung](https://www.postgresql.org/support/versioning/), [WeasyPrint API und Versionsmodell](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html).

### Bewusst nicht in V1

- Keine React-/Vue-SPA und kein separates REST-Backend.
- Kein Microservice-System, Kubernetes oder Service Mesh.
- Kein Redis/Celery nur auf Vorrat. Kurze Synchronisationen und PDF-Erzeugung laufen zunächst im Request mit harten Zeitlimits. Wenn produktive WebDAV-Latenzen das Nutzererlebnis gefährden, ist ein transaktionaler Job/Outbox-Worker die erste gezielte Erweiterung.
- Kein generisches Plugin-Framework. Adapter sind normale Python-Protokolle plus Dependency Injection an wenigen Kompositionspunkten.
- Keine PostgreSQL Row-Level Security als einzige Schutzschicht. Sie kann später als zusätzliche Hosted-Härtung geprüft werden, ersetzt aber weder Autorisierung noch tenant-gebundene Repositories.

## 3. Systemarchitektur

```text
Browser
  -> Django Views / Forms / Templates
       -> Application Services (Use Cases, Transaktionen, Autorisierung)
            -> Domain Models und Policies
            -> tenant-gebundene Repositories (Django ORM)
            -> WorkshopProvider
                 -> PretixAdapter [V1]
            -> native Workshop-Erfassung [später, direktes internes Modell]
            -> PdfRenderer
                 -> WeasyPrintAdapter [V1]
            -> StorageProvider
                 -> WebDavAdapter [V1]
                 -> InternalStorageAdapter [später]
                 -> DownloadOnlyAdapter [später]
       -> PostgreSQL
```

Abhängigkeitsrichtung: UI und Adapter dürfen die Anwendungsschicht aufrufen; die fachliche Kernlogik importiert keine Pretix-, Authentik-, Nextcloud- oder HTTP-Details. Die Grenzen bleiben pragmatisch: Django-Modelle dürfen zugleich Persistenzmodelle sein, solange externe Payloads nicht in die Fachmodelle durchsickern.

### Zentrale Use Cases

- `ListDocumentableWorkshops`
- `RefreshWorkshopFromProvider`
- `OpenDocumentationDraft`
- `SaveAttendanceAndFeedback`
- `FinalizeDocumentation`
- `RenderWorkshopDocument`
- `StoreGeneratedDocument`

`FinalizeDocumentation` führt ausschließlich die fachliche Finalisierung aus: Sperre/Versionsprüfung, fachliche Validierung und unveränderlichen Abschluss-Snapshot werden in einer kurzen lokalen Datenbanktransaktion atomar gespeichert; danach ist `Documentation.status = finalized`. Die Erreichbarkeit eines PDF-Renderers oder Storage-Providers beeinflusst diesen fachlichen Status nicht.

PDF-Erzeugung und Storage bilden einen separaten, wiederholbaren Prozess mit eigenem Status, beispielsweise `pending -> rendered -> stored` beziehungsweise `render_failed` oder `storage_failed`. Der Prozess arbeitet immer aus dem bereits finalisierten Snapshot, finalisiert die Dokumentation nicht erneut und ist über Snapshot-, Template- und Inhalts-Hashes idempotent. Während Rendering oder externen HTTP-/WebDAV-Aufrufen bleibt keine lang laufende Datenbanktransaktion offen. Kurze Transaktionen reservieren einen Arbeitsversuch oder speichern dessen Ergebnis; Netzwerkarbeit findet dazwischen außerhalb der Transaktion statt.

## 4. Repository-Struktur

```text
werkblatt/
├── pyproject.toml
├── compose.yaml
├── Dockerfile
├── .env.example
├── manage.py
├── config/                  # Settings, URLs, WSGI, Composition Root
├── src/werkblatt/
│   ├── organizations/       # Tenant, Mitgliedschaft, Rollen, Branding
│   ├── identities/          # interne User/Identity-Verknüpfung, OIDC
│   ├── workshops/           # internes Workshopmodell, Provider-Port
│   ├── documentation/       # Entwurf, Anwesenheit, Abschluss, Snapshot
│   ├── projects/            # Projekte, Logo-Metadaten und Zuordnungen
│   ├── integrations/
│   │   ├── pretix/
│   │   ├── oidc/
│   │   └── webdav/
│   ├── documents/           # PDF-Port, Templates, Storage-Port
│   ├── audit/               # sicherheitsrelevante, PII-arme Ereignisse
│   ├── web/                 # gemeinsame UI-Komponenten und Assets
│   └── static/werkblatt/    # ausgewählte Produktionsassets, Tokens
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── contract/
│   ├── pdf/
│   └── e2e/
├── docs/
│   ├── architecture/
│   ├── operations/
│   └── brand-assets.md
└── scripts/                 # deterministische Betriebs-/QA-Helfer
```

Keine Bezeichnungen wie `werkblatt_participant` im Fachschema. Der Produktname ist für Repository, Python-Package, statische Namespace-Pfade und Container sinnvoll; Fachobjekte bleiben neutral.

## 5. Datenmodell

Alle primären IDs sind UUIDs. Zeitpunkte werden als UTC gespeichert und mit einer organisationsbezogenen IANA-Zeitzone dargestellt. Änderbare Datensätze erhalten `created_at`, `updated_at` und bei konkurrierend editierbaren Entwürfen eine Versionsnummer.

### Organisation und Identität

| Entität | Wesentliche Felder / Regeln |
|---|---|
| `Organization` | `id`, `slug`, `name`, `status`, `timezone`, `default_locale`, Branding-/Kontaktfelder; `slug` global eindeutig. |
| `User` | interne, installationsweite Person: `id`, `display_name`, optionale normalisierte E-Mail, `is_active`; keine Tenantrolle direkt am User. |
| `Identity` | `user_id`, `kind` (`oidc`/`local`), `issuer`, `subject`, lokale Login-ID; Unique `(kind, issuer, subject)` für OIDC. Passwortdaten nur über Django-Auth. |
| `Membership` | `organization_id`, `user_id`, `role`, `status`; Unique `(organization_id, user_id)`. |
| `OidcProviderConfig` | tenantbezogene nicht-geheime Metadaten plus Referenz auf Secret; Issuer/Client-Zuordnung. |

### Workshops und Dokumentation

| Entität | Wesentliche Felder / Regeln |
|---|---|
| `Workshop` | `organization_id`, `source_type`, `external_reference`, Titel, Beginn/Ende, Ort, optionale `project_id`; Unique `(organization_id, source_type, external_reference)` wenn extern. |
| `WorkshopRegistration` | `organization_id`, `workshop_id`, providerbezogene stabile Referenz, Anzeigename, Importzeitpunkt, Quellstatus; keine vollständige Pretix-Bestellung speichern. |
| `WorkshopFacilitator` | `organization_id`, `workshop_id`, Anzeigename, optionaler `user_id`; Account ist nicht erforderlich. |
| `Documentation` | `organization_id`, `workshop_id`, Status `draft/finalized`, Planmäßig-Flag, Kurzbericht, strukturierte Statistik, Version, Bearbeiter, Abschlusszeitpunkt; höchstens eine aktive fachliche Dokumentation je Workshop. |
| `AttendanceEntry` | `organization_id`, `documentation_id`, optional `registration_id`, Name, Ursprung `registered/walk_in`, Anwesenheitsstatus; Unique für importierte Registrierung pro Dokumentation. |
| `DocumentationSnapshot` | unveränderliche JSON-Repräsentation der fachlichen Abschlussdaten, Schema-Version und Hash; Grundlage für reproduzierbare PDF-Neuerzeugung. |
| `GeneratedDocument` | `organization_id`, `documentation_id`, Snapshot-, Template- und Renderer-Version, PDF-Hash, Status (`pending/rendered/stored/render_failed/storage_failed`), MIME, Größe, sicherer Dateiname, Storage-Key, Versuchszähler und letzte sichere Fehlerklasse. |

Statistik wird beim Speichern aus den Einträgen berechnet, nicht vom Browser übernommen:

- `registered = Anzahl importierter Registrierungen`
- `present_registered = anwesende importierte Registrierungen`
- `walk_ins = anwesende spontan Ergänzte`
- `present_total = present_registered + walk_ins`
- `no_shows = registered - present_registered`

Damit ist das Beispiel `11 angemeldet, 9 tatsächlich, 3 No-Shows, 1 spontan` konsistent: 8 angemeldete Personen waren anwesend, plus 1 spontane Person.

### Projekte, Assets und Integrationen

| Entität | Wesentliche Felder / Regeln |
|---|---|
| `Project` | `organization_id`, Name, optionaler Code, Zeitraum, Aktivstatus. |
| `BrandAsset` | `organization_id`, Rolle (`organization/project/funder`), Dateimetadaten, Hash, validierter MIME-Typ, Abmessungen; Datei selbst über kontrollierten Asset-Storage. |
| `ProjectAsset` | tenantgeprüfte m:n-Zuordnung mit Reihenfolge und optionalem Zeitraum. |
| `IntegrationConfig` | `organization_id`, Typ, Status, nicht-geheime Einstellungen, Secret-Referenz, letzte Prüfung. In V1 können konkrete Tabellen für Pretix/WebDAV klarer sein; keine polymorphe JSON-Allzwecktabelle erzwingen. |

Denormalisiertes `organization_id` auf abhängigen fachlichen Tabellen ist Absicht: Es macht Tenant-Filter und zusammengesetzte Constraints möglich. Datenbank-Constraints oder modellseitige Validierung verhindern, dass etwa Workshop und Dokumentation unterschiedlichen Organisationen angehören.

## 6. Tenant-Isolation

### Request-Kontext

1. Die authentifizierte Identität wird internem `User` zugeordnet.
2. Der Tenant wird aus vertrauenswürdiger Routing-/Session-Konfiguration ermittelt, nicht aus einem versteckten Formularfeld.
3. Eine aktive `Membership` wird geprüft.
4. Erst dann entsteht ein unveränderlicher `OrganizationContext` für den Request.
5. Services und Repositories verlangen diesen Kontext explizit.

Auch wenn eine Installation in V1 zunächst nur eine Organisation konfiguriert, läuft jeder Zugriff durch denselben Mechanismus. Es gibt keinen globalen Fallback-Tenant in Fachservices und kein `Organization.objects.first()`.

### Durchsetzung

- Tenant-gebundene Manager/Repositories beginnen stets mit `organization_id=context.organization_id`.
- Objektzugriffe sind `(organization_id, object_id)`, nie nur `object_id`.
- Form-Choices werden tenantgefiltert; serverseitige Validierung prüft die Zugehörigkeit erneut.
- Cache-Keys enthalten Organisation, Provider und Konfigurationsversion.
- Dateipfade/Storage-Keys beginnen mit einer nicht erratbaren bzw. intern aufgelösten Tenant-ID; Downloads laufen durch Autorisierung, nicht durch öffentliche Pfade.
- Platform Admin ist keine implizite Datenleserrolle. Supportzugriff wäre später ein expliziter, auditierter Vorgang.
- Security-Tests erzeugen mindestens zwei Organisationen und versuchen systematisch Cross-Tenant-IDs in URL, Formular, API, Cache und Storage.

## 7. User- und Identity-Modell

`User` beschreibt die interne Person, `Identity` die Anmeldemethode und `Membership` deren Rolle in einer Organisation. Dadurch kann dieselbe Person später eine OIDC- und eine lokale Identität besitzen, ohne zwei fachliche Benutzerkonten zu erzeugen.

### OIDC in V1

- Authorization Code Flow mit PKCE, `state`, `nonce`, strikter Issuer-/Audience-/Signaturprüfung und enger Redirect-URI-Liste.
- Stabile Zuordnung ausschließlich über `(issuer, sub)`, niemals über E-Mail.
- Anzeigename und optionale E-Mail sind synchronisierbare Profilattribute, keine Autorisierungsquelle.
- Claims/Gruppen werden über konfigurierbare exakte Regeln auf Membership/Rolle abgebildet. Unbekannte oder fehlende Claims gewähren keinen Zugriff.
- Keine Authentik-Admin-API und keine Authentik-spezifische Kernlogik.
- Session-Cookies: `Secure`, `HttpOnly`, angemessenes `SameSite`, Rotation beim Login; kurze administrative und sinnvolle normale Session-Laufzeiten konfigurierbar.

### Lokale Accounts später

Django-Passwort-Hashing, Einladungs- und Reset-Tokens mit kurzer Laufzeit und Einmalverwendung, Rate-Limits und Deaktivierung. Das Datenmodell steht bereit; UI, Mailversand und lokale Login-Flows werden in V1 nicht gebaut.

## 8. Workshop-Provider

```python
class WorkshopProvider(Protocol):
    def list_workshops(self, context, window) -> list[ExternalWorkshop]: ...
    def get_workshop(self, context, reference) -> ExternalWorkshop: ...
    def list_registrations(self, context, reference) -> list[ExternalRegistration]: ...
```

Die Rückgabetypen sind neutrale DTOs. Ein Import-/Sync-Service ordnet sie dem internen `Workshop` und `WorkshopRegistration` zu. Pretix-Payloads werden nicht als Domänenobjekte verwendet.

### Pretix V1

- Offizielle API, tenantbezogene Base-URL/Organizer/Token-Konfiguration.
- Eventserien und Subevents werden explizit unterstützt: die externe Referenz enthält Event-Slug plus Subevent-ID, wo nötig.
- Paginierung, Timeouts, begrenzte Retries mit Jitter, verständliche Fehlerklassifikation und kurze Cache-Zeit.
- SSRF-Schutz: nur `https`, keine URL-Credentials, DNS-/IP-Prüfung gegen Loopback/private/link-local/reservierte Ziele nach jeder Auflösung, Redirects standardmäßig aus oder erneut vollständig validiert, feste Port-Policy, Response-/Zeitlimits.
- Nur erforderliche Felder übernehmen. Keine Zahlungs-, Adress- oder unnötigen Bestelldaten.
- Refresh ist bewusst möglich; nach Beginn der fachlichen Dokumentation überschreibt ein Sync keine manuell korrigierte Anwesenheit.

### Native/manuelle Workshops später

Manuell angelegte Workshops sind eine native Werkblatt-Quelle und kein künstlicher externer Provider. Die spätere Erfassungs-UI legt direkt dasselbe interne `Workshop`-Modell mit `source_type = native` (alternativ nach endgültiger Benennung `manual`) und ohne externe Referenz an. `WorkshopProvider` bleibt die Integrationsgrenze für Pretix und mögliche weitere externe Quellen. Ab dem internen Workshopmodell sind Dokumentationslogik, Berechtigungen, Teilnehmerverwaltung und PDF-Prozess für native und importierte Workshops identisch.

## 9. Storage-Provider

```python
class StorageProvider(Protocol):
    def put(self, context, key, content, content_type, if_absent=True) -> StoredObject: ...
    def get(self, context, key) -> BinaryIO: ...
    def delete(self, context, key) -> None: ...
    def healthcheck(self, context) -> StorageHealth: ...
```

### WebDAV/Nextcloud V1

- Dedizierter eingeschränkter technischer Account pro Organisation/Installation, kein Admin und kein persönlicher Account.
- Serverbasierte URL- und Credential-Konfiguration; Secrets gelangen weder in HTML noch Logs.
- Zielpfad logisch: `<tenant-prefix>/YYYY/MM/YYYY-MM-DD_slug_vNN.pdf`.
- Dateiname wird aus normalisiertem Titel erzeugt; der Storage-Key kommt nie direkt aus Benutzereingabe.
- `if_absent` bzw. vorherige Existenzprüfung verhindert stilles Überschreiben. DB-Record und Inhalts-Hash erlauben idempotente Wiederholung.
- Upload zunächst in temporären Namen, danach MOVE/atomare Finalisierung, sofern der Server dies zuverlässig unterstützt; sonst klar dokumentierter Fallback mit anschließender Verifikation.
- Nach Upload Größe/Hash soweit möglich verifizieren. Fehlgeschlagener Upload bleibt als wiederholbarer `storage_failed`-Status sichtbar.

### Spätere Provider

- `InternalStorageAdapter`: private persistente Objektspeicherung oder Volume, autorisierte Auslieferung und Lifecycle.
- `DownloadOnlyAdapter`: liefert die erzeugten Bytes an den Request, ohne dauerhafte PDF-Ablage; der fachliche Snapshot bleibt bestehen.

## 10. PDF-Konzept

PDF-Erzeugung und Speicherung bleiben getrennt. Ein versioniertes, ausschließlich aus validierten Snapshotdaten gespeistes HTML-Template wird mit lokalem CSS und lokalen freigegebenen Assets durch WeasyPrint gerendert.

Sicherheitsregeln:

- Kein beliebiges HTML aus Kurzbericht oder Organisationsdaten; Templates escapen standardmäßig.
- Keine externen HTTP-Ressourcen beim Rendern. Eigener URL-Fetcher erlaubt nur explizite lokale Asset-Verzeichnisse bzw. bereits validierte Binärdaten.
- SVG-/Bild-Uploads werden vor Verwendung validiert, begrenzt und vorzugsweise in eine sichere, kontrollierte Repräsentation überführt. Keine Skripte, externen Referenzen oder aktiven Inhalte.
- Renderer-Version, Template-Version, Snapshot-Hash und PDF-Hash werden gespeichert.

QA:

- deterministische synthetische Fixtures;
- Text-/Metadatenprüfung;
- Seitenrendering und visuelle Regression auf Referenzbildern;
- Varianten ohne Logo, mit einem und mehreren Logos, langen Namen/Berichten, mehreren Seiten und Sonderzeichen;
- A4-Druckprüfung und eingebettete Schrift;
- WeasyPrint-Upgrade nur nach visueller Freigabe.

Das endgültige Workshop-PDF wird erst in Phase 3 nach Analyse des realen Papierbogens vorgeschlagen und nach Rückmeldung implementiert. Die drei Ebenen bleiben getrennt: Werkblatt-Produktmarke, durchführende Organisation, Projekt/Förderung.

## 11. Brand-System 1.0.1

Das ZIP wurde vollständig analysiert. `README.md`, `brand.json`, Markdown-Guidelines, visuelle Dokumentation, QA-Bericht, QA-JSON, Lizenzen und Changelog sind berücksichtigt. Die dokumentierten SHA-256-Werte der beiden Master stimmen:

- `Werkblatt_Coloured.svg`: `27759b5e2c0ee2bc3ab196ec6ce942c20db544acac73a2fe54405abbba15f806`
- `Werkblatt.svg`: `b6504d6cdcffb9b078b113f4c9274f902409cf39753375049dc3f88f99a6c1b4`

Verbindliche Konsequenzen:

- Master unter `source-master/` werden nicht in der Anwendung bearbeitet oder rekonstruiert.
- In Phase 1 werden die für die Webanwendung benötigten Produktionsassets übernommen und in `docs/brand-assets.md` mit Quelle, Version, Zielpfad, Rolle und Hash inventarisiert: Primärlogo/Signet, Favicons, PWA-/App-Icons, CSS-Tokens sowie Inter einschließlich OFL-1.1- und Copyright-Dokumentation.
- `brand.json` wird zur Quelle für CSS-Tokens: `#004E55`, `#037A84`, `#3DB3B7`, `#A7DCE0` sowie die definierten Neutraltöne.
- Inter Regular 400 und SemiBold 600; Fontdateien und OFL-Lizenztext müssen separat aus offizieller Quelle eingebracht werden.
- Mindestgrößen und Schutzraum (`x = 1/8` der sichtbaren Signethöhe, rundum mindestens `1x`) werden in UI/PDF berücksichtigt.
- Auf dunklen Hintergründen nur die vorgesehene invertierte/weiße Produktionsvariante. Monochrom ist kein Umfärben des Farbsignets.
- Organisationslogo, Werkblatt-Produktmarke und optionale Software-/Hosting-Attribution sind getrennte Komponenten.

Produktionsassets für die Webanwendung in Phase 1: Primärlogo und bei tatsächlichem UI-Bedarf die invertierte Variante, Farbsignet, App-/Maskable-/Apple-Touch-Icons, Favicon-Satz, Brand-Tokens und Inter. Phase 3 übernimmt keine allgemeine Web-Branding-Grundlage mehr, sondern behandelt ausschließlich die PDF-/Dokumentanwendung des Werkblatt-CD sowie Organisations-, Projekt- und Förderlogos. Social-OG wird erst übernommen, wenn eine öffentliche Projektseite es tatsächlich nutzt.

## 12. Security- und Datenschutzkonzept

### Autorisierung und Websicherheit

- Deny-by-default, rollen- und tenantbezogene Policies in Application Services sowie objektbezogene Checks.
- Django-CSRF-Schutz, sichere Cookies, Security Headers und strikte `ALLOWED_HOSTS`/Origin-Konfiguration.
- Content Security Policy zunächst ohne Inline-Skripte, wo praktikabel; lokale Assets statt Drittanbieter-CDNs.
- Rate-Limits für Login, OIDC-Callback-Fehler, Refresh und teure Integrationsaktionen.
- Keine Stacktraces im Frontend; korrelierbare Fehler-ID ohne PII.
- Abhängigkeiten und Containerbasis regelmäßig gescannt; aktuelle Patchstände über kleine, geprüfte Updates.

### Datenminimierung

- Von Pretix nur stabile Referenz, erforderlicher Anzeigename und Workshopdaten übernehmen.
- E-Mail, Adresse, Zahlung und vollständige Order-Daten nicht speichern.
- Teilnehmernamen nicht in normale Logs, Metriken, Traces oder Fehlertexte.
- Aufbewahrung bleibt pro Organisation konfigurierbar; keine Frist wird vorgegeben. Lösch-/Anonymisierungs-Use-Cases und referenzielle Folgen werden vor Produktionsstart spezifiziert.

### Secrets

- Deployment-Secrets aus Container-/Environment-Secrets, nie aus Git oder Frontend.
- Tenant-Secrets in V1 vorzugsweise als Deployment-Secret-Referenzen, weil zunächst nur ein Tenant produktiv ist. Kein verfrühtes eigenes verschlüsseltes Secret-Vault-Schema.
- Vor Hosted-Multi-Tenant-Betrieb: etablierter Secret-Manager oder envelope-verschlüsselte Speicherung mit extern gehaltenem Master-Key und Rotationskonzept.

### Uploads

- Größen-, Pixel-, Dateityp- und MIME-Prüfung; Inhalte anhand von Magic Bytes dekodieren.
- Zufällige interne Dateinamen, private Ablage, keine Ausführung und kein direktes Serving aus Uploadverzeichnissen.
- SVG nur nach strenger Sanitization bzw. sichere Rasterisierung für nicht vertrauenswürdige Organisations-/Förderlogos; Original nur falls fachlich nötig und niemals unkontrolliert in HTML/PDF einbetten.

## 13. Self-Hosted-Betriebsmodell

V1-Compose enthält `web` und `db`; optional übernimmt ein vorhandener Reverse Proxy TLS. Ein Beispielprofil kann später einen Proxy ergänzen. Persistenz umfasst PostgreSQL und gegebenenfalls lokale temporäre/Asset-Daten, nicht den Container-Layer.

- `.env.example` enthält nur Platzhalter und dokumentierte sichere Defaults.
- Startup führt keine unkontrollierten destruktiven Migrationen aus; Migrationen sind ein bewusster Release-Schritt.
- Healthchecks trennen Liveness und Readiness; externe Integrationen machen die App nicht pauschal unready.
- Backup: konsistenter `pg_dump` plus notwendige persistente Assets und Konfiguration; Restore wird automatisiert getestet.
- Releases sind unveränderlich getaggt; Update-Doku nennt Migration, Backup, Rollback-Grenzen und Breaking Changes.
- Langfristiger Setup-Pfad: Compose starten, browserbasierte Ersteinrichtung, lokale Accounts, manuelle Workshops und interner/download-only Storage. Diese UI wird nicht in V1 vorgetäuscht.

## 14. Hosted-Multi-Tenant-Modell

Zunächst dieselbe Anwendung und dasselbe Schema. Shared-Database/Shared-Schema ist für kleine Organisationen betrieblich am einfachsten, wenn die oben beschriebene Isolation konsequent umgesetzt und getestet wird.

- Jede fachliche Tabelle ist tenantgebunden.
- Tenantkonfiguration, Caches, Secrets, Assets und Storage-Pfade sind getrennt.
- Platform-Administration verwaltet Organisationen/Status, besitzt aber keine automatische Datenleseberechtigung.
- Organisationsdeaktivierung sperrt Zugriff und Synchronisation, löscht aber nicht automatisch Daten.
- Per-Tenant-Export und Löschkonzept werden als spätere Application Services vorbereitet.
- Vor Aufnahme der ersten Partnerorganisation ist ein eigener Tenant-Isolation-/IDOR-Review ein Release-Gate. Optional wird PostgreSQL RLS dann als zweite Schutzschicht evaluiert.
- `software_author/project_origin` und `hosting_provider` sind getrennte Deployment-Metadaten. Eine Hosting-Angabe erscheint nur bei entsprechender Konfiguration.

## 15. Migrationen und Versionsstrategie

- Django-Schemamigrationen werden versioniert und in CI auf Konflikte sowie frische Installation geprüft.
- Datenmigrationen sind klein, wiederholbar und möglichst vorwärtskompatibel.
- Expand/contract bei Änderungen, die Rollback oder gemischte Versionsstände betreffen: neue nullable Felder/Tabellen, Daten füllen, Anwendung umstellen, erst später Altstruktur entfernen.
- Dokumentations-Snapshots, PDF-Templates und Provider-Mappings besitzen eigene Schema-/Versionsfelder; historische Nachweise bleiben interpretierbar.
- PostgreSQL-Major-Upgrades sind explizite Betriebsprojekte mit Backup- und Restore-Test; Minor-Updates werden zeitnah eingespielt.

## 16. Teststrategie

| Ebene | Fokus |
|---|---|
| Unit | Statistik, Statusübergänge, Dateinamen, Rollen, Normalisierung, Provider-Mapping. |
| Integration | PostgreSQL-Constraints, Transaktionen, Django-Views, OIDC-Callback, Pretix-/WebDAV-HTTP über Mockserver. |
| Contract | Aufgezeichnete, anonymisierte bzw. synthetische Pretix-/WebDAV-Verträge; keine echten personenbezogenen Fixtures. |
| Security | Zwei-Tenant-Matrix, IDOR, Rollen, CSRF, SSRF, Uploads, Secret-/PII-Logging. |
| PDF | Inhalt, Seitenzahl, Fonts, Vektorgrafik, visuelle Regression und lange Grenzfälle. |
| E2E | Wenige kritische Wege: Login -> Workshop -> Anwesenheit -> Abschluss -> PDF/Storage sowie Wiederholungs-/Fehlerfall. |
| Operations | frischer Compose-Start, Migration, Healthcheck, Backup und Restore. |

CI-Gates: Format/Lint, Unit/Integration, Migration-Check, Produktionsbuild, Container-Scan, Secret-Scan, Dependency-Scan und ausgewählte E2E/PDF-Regression. Keine automatische Produktionseinspielung.

## 17. Abgrenzung: V1 / vorbereitet / später

### V1 implementieren

- Eine konfigurierte Organisation, aber vollständig tenantgebundene Zugriffe.
- OIDC/Authentik über Standard-OIDC, Membership und Rollen.
- Pretix inklusive Eventserien/Subevents, Workshopliste und Teilnehmerimport.
- Anwesenheit, spontane Teilnehmende, Durchführende, Kurzbericht, Entwurf und Abschluss.
- Für den aktuellen Workflow notwendige Projekte/Förderlogos.
- Versioniertes PDF nach Papierbogenanalyse und Freigabe.
- WebDAV/Nextcloud, Docker, PostgreSQL, Tests, CI, Backup/Restore.
- Werkblatt Brand System 1.0.1 mit ausgewählten unveränderten Produktionsassets.

### Jetzt strukturell vorbereiten, nicht als leere UI bauen

- mehrere Organisationen, weitere OIDC-Provider, lokale Identitäten;
- manuelle Workshops und weitere Workshop-Provider;
- interner und Download-only Storage;
- organisationsbezogenes Branding, Projekt-/Logo-Presets;
- Ersteinrichtung und Datenexport;
- konfigurierbare Herkunft-/Hosting-Attribution und spätere Internationalisierung.

### Später

- Einladungen, Passwortreset und komplette lokale Accountverwaltung;
- Hosted-Plattformverwaltung und Partner-Onboarding;
- Statistik-Dashboard, CSV/Excel-/Organisations-Export;
- mehrere PDF-Templates, separate Anwesenheitslisten, Signaturen;
- weitere Event-/Storage-Provider;
- Retention-/Löschoberfläche nach fachlicher Fristentscheidung.

## 18. Implementierungsphasen und Abhängigkeiten

1. **Phase 1 - Fundament und Web-Branding:** Repository, Tooling, Docker/PostgreSQL, Organization/User/Identity/Membership, OIDC, Rollen, Pretix-Port/Adapter, Workshopmodell und Liste. Außerdem werden Primärlogo/Signet, Favicons, PWA-/App-Icons, CSS-Tokens und Inter samt Lizenzdokumentation aus Brand System 1.0.1 nachvollziehbar übernommen. Abhängigkeit: OIDC-/Pretix-Konfiguration und bestätigte vorhandene URLs; unbekannte Projekt-/Repository-URLs bleiben Platzhalter.
2. **Phase 2 - Dokumentation:** Entwurf, Teilnehmer-Snapshot, Anwesenheit, Walk-ins, Durchführende, Feedback, Abschlusszustände und Statistik. Abhängigkeit: fachliche Klärung zu Bearbeitung/Unterschriften/Pflichtfeldern.
3. **Phase 3a - Analyse-Gate:** realen Papierbogen datenschutzkonform analysieren; Feld- und Layoutvorschlag, Logo-/Organisationsbedarf und offene Fragen liefern; dann stoppen.
4. **Phase 3b - PDF/Dokumentbranding/Storage:** nach Freigabe die PDF-/Dokumentanwendung des Werkblatt-CD implementieren, Organisations-/Projekt-/Förderlogos integrieren und WebDAV anbinden. Die Webanwendungs-Assets sind bereits Bestandteil von Phase 1. Abhängigkeit: Papierbogen, Organisations-/Projekt-/Förderlogos, Angaben und Storage-Testzugang.
5. **Phase 4 - Produktionsreife:** vollständige Security-/Tenant-Tests, CI, Image, generische Backup-/Restore-Dokumentation und Self-Hosting-Preflight. Konkrete Rollouts werden ausschließlich in der jeweiligen Infrastruktur dokumentiert.

Jede Phase endet mit Tests, nachvollziehbarem Zwischenstand und Freigabe. Phase 0 ist freigegeben; Phase 1 beginnt nach einem ausdrücklichen Startsignal und Bereitstellung der dafür erforderlichen OIDC-/Pretix-Konfiguration.

## 19. Lizenzvorschlag - Entscheidung erforderlich

Zwei sinnvolle Richtungen:

- **AGPL-3.0-or-later:** Änderungen, die als Netzwerkdienst angeboten werden, müssen den Nutzenden als Quellcode zugänglich gemacht werden. Das schützt den offenen Charakter auch im Hosted-Betrieb, kann aber kommerzielle Integratoren abschrecken und erfordert sorgfältige Kompatibilitätsprüfung.
- **EUPL-1.2:** EU-orientierte Copyleft-Lizenz, in vielen europäischen Verwaltungskontexten gut anschlussfähig und mit benannten kompatiblen Lizenzen. International weniger geläufig als GPL/AGPL; der Netzwerk-Copyleft-Effekt und Kompatibilitätsweg sollten juristisch für das gewünschte Hostingmodell geprüft werden.

Falls maximale Verbreitung wichtiger ist als Copyleft, wäre Apache-2.0 die permissive Alternative mit ausdrücklicher Patentklausel. Empfehlung für die Diskussion: AGPL-3.0-or-later, wenn verhindert werden soll, dass ein Dritter eine verbesserte proprietäre Hosted-Version betreibt. Keine Lizenzdatei wird ohne Zustimmung angelegt. Die Marken-/Logo-Nutzungsregeln sind separat zu entscheiden; eine Softwarelizenz lizenziert das Branding nicht automatisch.

## 20. Offene Fragen vor Phase 1

### Beantwortet / entschieden

1. Stack: **Django 5.2 LTS + serverseitige Templates/HTMX + PostgreSQL 17** ist freigegeben.
2. Lizenz: **AGPL-3.0-or-later** wird wegen des Netzwerk-Copyleft-Effekts bevorzugt weitergeprüft; die endgültige Lizenzentscheidung erfolgt separat.
3. URLs: Es werden nur endgültig bekannte URLs eingetragen. Unbekannte Projekt- und Repository-URLs bleiben ausdrücklich Platzhalter.
4. Authentik: Issuer/Discovery-URL, Client-ID, Redirect-URIs und relevante Claims werden zum Start von Phase 1 bereitgestellt; das Client-Secret ausschließlich als Environment Secret.
5. Pretix: Base-URL, Organizer, repräsentative Event-/Subevent-Testdaten und Token werden zum Start von Phase 1 bereitgestellt; der Token ausschließlich als Environment Secret.
6. Rollen: Der Pilot verwendet ausschließlich `Organization Admin` und `Workshop User`.

### Vor Phase 2 beantwortet / entschieden

7. Abgeschlossene Dokumentationen dürfen alltagstauglich zur Korrektur geöffnet werden. Jeder erneute Abschluss erzeugt automatisch eine neue unveränderliche Revision mit Snapshot; frühere Revisionen bleiben erhalten. Es gibt keinen separaten Freigabe- oder Entsperrprozess.
8. Alle aktiven `Workshop User` und `Organization Admin` dürfen Dokumentationen der eigenen Organisation sehen, Entwürfe bearbeiten und abgeschlossene Dokumentationen wieder öffnen. `Organization Admin` besitzt dabei kein exklusives fachliches Recht. Organisationsübergreifender Zugriff ist ausgeschlossen.

### Spätestens vor Phase 3

9. Bitte den aktuellen Papier-Workshopbogen bereitstellen. Bei realen Daten behandle ich ihn ausschließlich lokal, committe und protokolliere ihn nicht.
10. Organisations-, Projekt- und Förderlogos sowie konkrete Texte sind Laufzeitdaten der jeweiligen Installation und werden nicht in das allgemeine Software-Repository übernommen.
11. Welche Nextcloud/WebDAV-Testdaten, Zielstruktur und Rechte stehen bereit? Dedizierter eingeschränkter technischer Account empfohlen.
12. Soll Inter im Repository selbst gehostet werden? Dann benötige ich die freigegebene offizielle Bezugsquelle und werde OFL-1.1 samt Copyright-Hinweisen aufnehmen.
13. Welche Aufbewahrungs- und Löschregeln sollen für Teilnehmernamen, strukturierte Dokumentationen und erzeugte PDFs gelten? Keine Frist wird ohne Vorgabe gewählt.
14. Optionale Software- und Hosting-Attributionen werden getrennt und über Installationseinstellungen konfiguriert.

## 21. Freigabe-Gate

Phase 0 ist mit den Präzisierungen vom 28. August 2026 freigegeben und abgeschlossen. Anwendungscode, Repository-Grundgerüst, Datenbankmigrationen und Brandassets werden erst nach dem ausdrücklichen Startsignal für Phase 1 angelegt. Eine Lizenzdatei folgt weiterhin erst nach der separaten endgültigen Lizenzentscheidung.
