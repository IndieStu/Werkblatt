# Phase 3a: Dokumentvorlagen, Assets und PDF-Konzept

Status: vollständig konkretisierter Vorschlag zur fachlichen Freigabe
Stand: 28. August 2026  
Scope: Analyse und Architektur; keine Phase-3b-Implementierung

## 1. Ergebnis in Kürze

Werkblatt erhält in V1 organisationsbezogene, wiederverwendbare Dokumentvorlagen. Eine Vorlage bündelt Projekt-/Programmtitel, optionale Texte, ausgewählte versionierte Logos, einfache Zusatzfelder und eine kleine Menge definierter Dokumentausgaben. Förderer, Projekte und Zircula-spezifische Namen lösen keine Programmlogik aus.

Die Verwaltungsoberfläche bleibt fachlich verständlich:

1. Organization Admin lädt ein Logo in die Asset-Bibliothek.
2. Der Admin benennt und kategorisiert es.
3. Der Admin erstellt eine Dokumentvorlage, wählt Logos, Ausgaben und Zusatzfelder und aktiviert die Vorlage.
4. Ein bestehender aktiver Vorlagenstand wird einem Workshop zugeordnet.
5. Workshop User sehen die daraus entstehenden Anforderungen, können vorab eine Teilnahmeliste erzeugen und dokumentieren später Anwesenheit, Bericht und Zusatzfelder.
6. Beim Abschluss friert die Dokumentationsrevision sämtliche renderrelevanten Definitionen, Werte und Asset-Versionen ein.
7. PDF-Rendering und Storage folgen weiterhin als eigener wiederholbarer Prozess außerhalb der Finalisierungstransaktion.

Es wird kein freier Layouteditor, universeller Formbuilder oder digitales Unterschriftssystem gebaut.

## 2. Fachliche Begriffe

| Begriff | Bedeutung |
|---|---|
| Brand Asset | Verständlich benanntes Logo oder anderes freigegebenes Markenasset einer Organisation. |
| Asset-Version | Unveränderliche konkrete Originaldatei samt sicherer technischer Repräsentation und Metadaten. |
| Dokumentvorlage | Wiederverwendbare fachliche Identität, beispielsweise „Klimaschutz im Alltag 2026“. |
| Vorlagenstand | Unveränderliche interne Version der vollständigen Vorlagenkonfiguration. |
| Dokumentausgabe | Eine definierte Ausgabeart wie Abschlussdokument oder druckbare Teilnahmeliste. |
| Zusatzfeld | Ein durch die Vorlage definiertes, kontrolliert typisiertes Eingabefeld. |
| Abschluss-Snapshot | Unveränderliche Datenbasis einer Dokumentationsrevision einschließlich der damals verwendeten Vorlagenkonfiguration. |

## 3. Datenmodell für Brand Assets

Das Modell trennt die verständliche Asset-Identität von den unveränderlichen Dateien.

### `BrandAsset`

- `id`: UUID
- `organization_id`: zwingender Tenant
- `display_name`: frei verständlicher und innerhalb der Organisation eindeutiger Name
- `default_role`: `organization`, `project_program`, `funder`, `client`, `other`
- `status`: `active`, `inactive`
- `current_version_id`: aktuelle freigegebene Asset-Version
- `created_by`, `updated_by`, `created_at`, `updated_at`

### `BrandAssetVersion`

- `id`: UUID
- `organization_id`
- `asset_id`
- `number`: fortlaufend innerhalb des Assets
- `original_filename`: nur Anzeige/Audit, niemals Storage-Key
- `media_type`: in V1 ausschließlich `image/svg+xml` oder `image/png`
- `byte_size`, `width`, `height`: soweit für das Format bestimmbar
- `sha256`
- `original_storage_key`: private Originaldatei
- `safe_rendition_storage_key`: geprüfte Repräsentation für Preview und Rendering
- `validation_profile_version`: Version des angewendeten Prüfprofils
- `created_by`, `created_at`

Asset-Versionen sind unveränderlich. „Logo ersetzen“ erzeugt eine neue Version und setzt sie nach erfolgreicher Prüfung als aktuell. Historisch referenzierte Versionen werden nicht gelöscht. In V1 gibt es Deaktivieren beziehungsweise Archivieren statt destruktivem Löschen.

Die denormalisierte `organization_id` wird auf beiden Tabellen geführt. Services prüfen zusätzlich, dass Asset, Version und Organisation zusammengehören.

### Organisationsprofil

Das bestehende Organisationsmodell wird in V1 um ein optionales, über die normale Werkblatt-Oberfläche pflegbares Organisationsprofil ergänzt. Vorgesehen sind Organisationsname, Anschrift, Website, E-Mail und Telefonnummer. Dokumentvorlagen bestimmen, welche vorhandenen Angaben in einer Ausgabe erscheinen. Für interne Zircula-Bögen sind außer Name und Logo zunächst keine Kontaktdaten erforderlich. Das Profil bleibt organisationsbezogen und erzeugt keine neue fachliche Domäne.

## 4. Datenmodell für Dokumentvorlagen

### `DocumentTemplate`

- `id`: UUID
- `organization_id`
- `name`: interner, frei vergebener Vorlagenname; innerhalb der Organisation eindeutig
- `status`: `active`, `inactive`
- `current_version_id`: aktuell freigegebener Stand
- `is_default`: höchstens eine aktive Standardvorlage je Organisation
- `created_by`, `updated_by`, `created_at`, `updated_at`

### `DocumentTemplateVersion`

- `id`: UUID
- `organization_id`
- `template_id`
- `number`: interne fortlaufende Version
- `project_title`
- `subtitle`: optional
- `funding_text`: optional
- `configuration_schema_version`
- `created_by`, `created_at`

Ein Vorlagenstand ist nach seiner Aktivierung unveränderlich. Die normale UI spricht von „Vorlage bearbeiten“ und „Änderungen speichern“, nicht von einem komplexen Veröffentlichungsprozess. Intern wird beim Speichern einer geänderten aktiven Vorlage ein neuer Vorlagenstand erzeugt und als aktuell markiert.

### `TemplateAssetPlacement`

- `id`, `organization_id`, `template_version_id`, `asset_version_id`
- `role`: Rolle dieses Logos in genau dieser Vorlage
- `zone`: `header`, `project` oder `funding_footer`
- `sort_order`
- `enabled`
- `show_funded_by_label`: optionale Anzeige „Gefördert durch“ in der zugehörigen Logo-Zone
- optional `accessible_name` für barrierearme Metadaten

Die Organisation wählt damit pro Logo die vorgesehene Dokumentzone und die Reihenfolge innerhalb dieser Zone. Die konkrete Geometrie folgt weiterhin dem stabilen Layout der Ausgabeart. V1 bietet keine freie Pixelpositionierung, Größenregler oder Drag-and-Drop-Platzierung.

## 5. Vorlagenversionierung

Das einfache fachliche Verhalten lautet:

- Eine neue Workshop-Zuordnung verwendet den aktuell aktiven Vorlagenstand.
- Eine bestehende Workshop-Zuordnung bleibt auf ihrem gewählten Stand fixiert.
- Ändert ein Admin die Vorlage, wechseln bestehende Workshops nicht stillschweigend.
- Solange eine Dokumentation Entwurf ist, kann ein berechtigter Nutzer ausdrücklich „auf aktuellen Vorlagenstand aktualisieren“. Werkblatt zeigt vorher an, wenn dadurch Zusatzfelder oder Ausgaben geändert werden.
- Nach einem Abschluss bleibt die zugehörige Revision vollständig unverändert.
- Wird eine abgeschlossene Dokumentation wieder geöffnet, verwendet sie standardmäßig weiterhin den zuletzt zugeordneten Vorlagenstand. Ein bewusster Wechsel vor dem erneuten Abschluss ist möglich und wird in der neuen Revision sichtbar.

Damit sind Förderanforderungen für einen Workshop früh stabil, während zukünftige Workshops Aktualisierungen erhalten können.

## 6. Zuordnung zu Workshop und Dokumentation

### `WorkshopTemplateAssignment`

- `id`, `organization_id`, `workshop_id`
- `template_id`, `template_version_id`
- `assigned_by`, `assigned_at`, `updated_at`

Pro Workshop existiert höchstens eine aktive Zuordnung. Die redundante Template-ID erleichtert die Anzeige, die Version ist die fachlich wirksame Referenz.

Die Auswahl erfolgt möglichst bei Importprüfung oder manueller Anlage. Ohne besondere Anforderungen wird automatisch die aktive Standardvorlage angeboten. Gibt es keine Standardvorlage, muss spätestens vor der ersten vorlagenabhängigen Ausgabe beziehungsweise vor Finalisierung eine Vorlage gewählt werden.

Die Dokumentation selbst speichert ihre Zusatzfeldwerte. Der Abschluss-Snapshot übernimmt anschließend eine vollständige Kopie der verwendeten Vorlagen- und Felddefinitionen; er verlässt sich nicht nur auf Fremdschlüssel.

Pretix und native Workshops verwenden ab dem internen Workshopmodell exakt denselben Ablauf.

## 7. Dokumentausgaben

Eine Vorlage kann mehrere Ausgaben definieren. V1 kennt ausschließlich folgende Typen:

### `final_report`

Abschlussdokument mit Workshopdaten, Statistik, Durchführenden, Bericht, ausgewählten Zusatzfeldern und Logo-/Förderbereich. Namen tatsächlich anwesender Personen sind konfigurierbar und standardmäßig ausgeschaltet.

### `attendance_sheet`

Vor dem Workshop erzeugbare Druckliste mit angemeldeten Namen, freien Zeilen und optionaler Unterschriftsspalte. Die unterschriebene Papierfassung wird in V1 nicht als strukturierte Signatur gespeichert.

### `anonymized_report`

Datensparsame Abschlussfassung ohne Namen. Sie verwendet aggregierte Statistik und dafür freigegebene Zusatzfelder.

### `TemplateOutputDefinition`

- `id`, `organization_id`, `template_version_id`
- `kind`: einer der drei festen Typen
- `display_name`: verständliche Bezeichnung
- `enabled`, `sort_order`
- `include_participant_names`
- `include_signature_column`: nur für Teilnahmeliste
- `include_statistics`
- `include_report`
- `include_facilitators`

Die erlaubten Optionen werden je Ausgabetyp serverseitig begrenzt. Beispielsweise kann eine anonymisierte Ausgabe keine Klarnamen aktivieren. V1 benötigt keine frei programmierbaren Reportdefinitionen.

Vorab erzeugte Teilnahmelisten beziehen sich auf Workshop, Vorlagenstand, Asset-Versionen und einen eigenen Eingabe-Snapshot. Abschlussausgaben beziehen sich zusätzlich auf die konkrete Dokumentationsrevision. Der bereits in Phase 0 vorgesehene `GeneratedDocument`-Prozess muss deshalb einen Workshop und optional eine Abschlussrevision referenzieren können.

## 8. Minimales Custom-Field-Modell

V1 unterstützt:

- `short_text`
- `long_text`
- `integer`
- `decimal`
- `boolean`
- `choice`
- `date`

Eine separate technische Feldart „Statistik“ ist nicht erforderlich. Aggregierte Angaben sind Ganzzahlfelder, die über eine Darstellungsoption im Statistikbereich ausgegeben werden können.

### `TemplateCustomFieldDefinition`

- `id`: Identität innerhalb eines Vorlagenstands
- `stable_key`: stabile UUID zur Zuordnung zwischen Vorlagenständen
- `organization_id`, `template_version_id`
- `label`, optional `help_text`
- `field_type`
- `required`
- `sort_order`
- optional typisierter `default_value`
- `choice_options`: nur bei Auswahl, als geordnete Liste geprüfter Werte und Labels
- `presentation`: `regular` oder `aggregate_statistic`
- `usage`: `internal_only` oder `include_in_selected_outputs`
- Zuordnung zu erlaubten Ausgabearten
- `active`

### `DocumentationCustomFieldValue`

- `id`, `organization_id`, `documentation_id`
- `field_stable_key`
- zum Typ passende Wertespalte beziehungsweise streng validierter typisierter Wert
- `updated_by`, `updated_at`

Für V1 werden Felddefinitionen flach und ohne Abhängigkeiten dargestellt. Keine Formeln, Skripte, bedingte Sichtbarkeit, verschachtelten Gruppen oder benutzerdefinierte Validierung.

Beim Wechsel des Vorlagenstands werden Werte anhand des `stable_key` übernommen, wenn Feldtyp und Bedeutung kompatibel sind. Nicht mehr verwendete Werte bleiben intern nachvollziehbar, werden aber nicht in neue Ausgaben übernommen. Inkompatible Änderungen verlangen eine bewusste Neueingabe.

## 9. Abschluss-Snapshot und Reproduzierbarkeit

Jede `DocumentationRevision.snapshot` erhält zusätzlich zu den bereits vorhandenen Workshop-, Teilnehmer-, Durchführenden- und Statistikdaten:

- Vorlagen-ID, Vorlagenname und interne Versionsnummer
- vollständige renderrelevante Vorlagenkonfiguration mit Schema-Version
- ausgewählte Dokumentausgaben und alle wirksamen Optionen
- Projekt-/Programmtitel, Untertitel, Fördertexte
- konkrete Asset-Versionen mit Assetname, Rolle, Reihenfolge, MIME-Typ und SHA-256
- sichere interne Referenz auf die unveränderliche Asset-Datei
- vollständige damalige Custom-Field-Definitionen einschließlich Label, Typ und Ausgabezuordnung
- validierte Custom-Field-Werte
- Einstellung zur Ausgabe von Klarnamen
- Renderer- und später Template-Code-Version im erzeugten Dokumentdatensatz

Der Abschluss bleibt eine kurze lokale Transaktion. Er kopiert Konfiguration und Werte in den unveränderlichen Snapshot und setzt den fachlichen Status. Er rendert kein PDF und führt keinen Storage-Aufruf aus.

Der nachgelagerte Prozess erzeugt für jede gewünschte Ausgabe einen eigenen idempotenten Datensatz. Dessen Schlüssel berücksichtigt mindestens Revision beziehungsweise Vorab-Snapshot, Ausgabeart, Rendering-Template-Version und Inhalts-Hash. Ein Storage-Fehler verändert den fachlichen Abschluss nicht.

Historische Reproduktion setzt voraus, dass referenzierte Asset-Versionen und der interpretierbare Snapshot erhalten bleiben. Eine spätere Vorlagen- oder Logoänderung wird niemals dynamisch in ein altes Dokument eingelesen.

## 10. Upload-, Validierungs- und Preview-Konzept

### Unterstützte Formate in V1

- SVG (`image/svg+xml`), maximal 2 MiB
- PNG (`image/png`), maximal 10 MiB

JPEG wird in V1 nicht angeboten. Für die vorhandene FHB-Datei liegt eine PNG-Alternative vor. Die Beschränkung vermeidet in V1 zusätzliche Erwartungen an Transparenz und Hintergrundbehandlung; eine spätere kontrollierte Erweiterung bleibt möglich.

Für Rastergrafiken gelten maximal 8.000 Pixel je Kante und maximal 40 Megapixel. Die Prüfung erfolgt anhand vollständig dekodierter Bilddaten, nicht nur anhand des Headers.

### Prüfablauf

1. Upload landet unter zufälligem temporärem Namen außerhalb öffentlich ausgelieferter Pfade.
2. Dateigröße wird vor vollständiger Verarbeitung begrenzt.
3. Magic Bytes beziehungsweise XML-Struktur und deklarierter MIME-Typ müssen zusammenpassen.
4. PNG wird vollständig mit einer gepflegten Bildbibliothek dekodiert, auf Abmessungen, Pixelgrenze, beschädigte Daten und unerlaubte Zusatzinhalte geprüft.
5. SVG wird mit deaktivierten DTDs und externen Entitäten geparst.
6. SVG mit `script`, Event-Handlern, `foreignObject`, externen URLs, eingebetteten Remote-Schriften, `@import`, aktiven Animationen oder nichtlokalen Referenzen wird abgewiesen.
7. Zulässige lokale Fragmentreferenzen werden kontrolliert; CSS- und `url(...)`-Werte werden separat geprüft.
8. Erst nach erfolgreicher Validierung werden Original, SHA-256 und sichere Repräsentation dauerhaft gespeichert.

Werkblatt verändert das Original nicht. Für Browser-Vorschauen wird serverseitig eine sichere PNG-Rendition erzeugt. Für die PDF-Ausgabe kann ein geprüftes, normalisiertes SVG oder eine hochauflösende sichere Rasterrepräsentation verwendet werden. Diese technische Ableitung wird versioniert und ist keine gestalterische Bearbeitung.

Originaldateien werden privat gespeichert und nie direkt als aktive Webinhalte unter einer öffentlichen Media-URL ausgeführt. Preview und Download laufen über tenantgeprüfte Endpunkte mit sicheren `Content-Type`-, `Content-Disposition`- und `X-Content-Type-Options: nosniff`-Headern.

Verständliche Fehler unterscheiden mindestens: nicht unterstütztes Format, Datei zu groß, Bildabmessungen zu groß, beschädigte Datei und unsicheres SVG.

## 11. Berechtigungsmodell

### Organization Admin

- Asset-Bibliothek ansehen
- Assets hochladen, benennen, kategorisieren, versionieren und aktiv/inaktiv setzen
- Dokumentvorlagen erstellen, bearbeiten, aktivieren und deaktivieren
- Standardvorlage festlegen
- Logo-Reihenfolge, Ausgaben und Zusatzfelder konfigurieren

### Workshop User und Organization Admin

- aktive Vorlagen der eigenen Organisation ansehen und einem Workshop zuordnen
- bei Entwürfen einen bewussten Wechsel auf einen anderen aktiven Vorlagenstand vornehmen
- vorab definierte Teilnahmelisten erzeugen
- vorlagenbezogene Zusatzfelder ausfüllen
- Dokumentationen entsprechend den bestehenden Phase-2-Regeln bearbeiten, finalisieren und wieder öffnen
- erzeugte Dokumente der eigenen Organisation ansehen

Eine spätere feinere Rolle ist für V1 nicht notwendig. Jede Aktion beginnt mit dem serverseitigen Organisationskontext; IDs im Request bestimmen niemals den Tenant.

## 12. UX: Asset-Bibliothek

Navigation: `Einstellungen -> Logos & Assets`, nur für Organization Admin sichtbar.

### Übersicht

Karten oder kompakte Zeilen zeigen:

- sichere Vorschau
- Anzeigename
- Kategorie
- SVG oder PNG und gegebenenfalls Abmessungen
- aktuelle Versionsnummer und Upload-Datum
- aktiv/inaktiv
- Hinweis, in wie vielen aktiven Vorlagen das Asset verwendet wird

### Neues Asset

1. Datei auswählen oder ablegen.
2. Anzeigename vergeben.
3. Standardkategorie auswählen.
4. Upload prüfen lassen.
5. Vorschau und erkannte Metadaten kontrollieren.
6. Speichern.

### Asset bearbeiten

Name, Kategorie und Status sind änderbar. „Neue Version hochladen“ ist eine eigene klare Aktion. Vor dem Aktivieren der neuen Version zeigt Werkblatt alte und neue Vorschau sowie die betroffenen aktiven Vorlagen. Historische Dokumente bleiben unverändert.

Deaktivierte Assets bleiben in historischen Ansichten sichtbar, können aber nicht neu in Vorlagen aufgenommen werden. Ein in einer aktiven Vorlage verwendetes Asset kann deaktiviert werden; die UI warnt, und die Vorlage behält ihren fixierten Stand. Beim nächsten Bearbeiten der Vorlage muss ein Ersatz gewählt oder die Verwendung bewusst bestätigt werden.

## 13. UX: Dokumentvorlage bis Abschluss

### Vorlage erstellen

Ein geführtes Formular mit vier Abschnitten, nicht als Layoutdesigner:

1. **Grunddaten:** Vorlagenname, Projekt-/Programmtitel, Untertitel, Fördertext, Standardvorlage ja/nein.
2. **Logos:** aktive Assets auswählen, Rolle und Reihenfolge festlegen; Vorschau der standardisierten Logozeile.
3. **Ausgaben:** Abschlussdokument, Teilnahmeliste und/oder anonymisierte Fassung aktivieren; erlaubte Optionen wählen.
4. **Zusatzfelder:** Felder hinzufügen, typisieren, sortieren, Pflichtstatus und Ausgabezuordnung festlegen.

Im Logoabschnitt werden zusätzlich die Zone und die optionale Beschriftung „Gefördert durch“ gewählt. Vor Aktivierung zeigt eine Zusammenfassung fehlende Pflichtkonfiguration und datenschutzrelevante Optionen wie Klarnamenausgabe.

### Workshop zuordnen

Workshopliste und Dokumentationskopf zeigen die ausgewählte Vorlage. Bei neuen Workshops wird die Standardvorlage vorausgewählt. Berechtigte Nutzer können eine andere aktive Vorlage wählen. Erforderliche Zusatzfelder und verfügbare Ausgaben sind sofort sichtbar.

### Vor dem Workshop

Wenn die Vorlage eine Teilnahmeliste definiert, erscheint „Teilnahmeliste erzeugen“. Sie verwendet den fixierten Vorlagenstand und die aktuell importierten Anmeldungen. Ein späterer Pretix-Sync kann eine neue Listenfassung erzeugen; vorhandene Dateien werden nicht überschrieben.

### Nach dem Workshop

Workshop User markieren Anwesenheit, ergänzen spontane Personen, pflegen Durchführende, Bericht und vorlagenbezogene Zusatzfelder. Pflichtfelder werden vor dem Abschluss validiert.

### Abschluss

Vor dem Abschluss zeigt Werkblatt:

- verwendete Vorlage und Stand
- zu erzeugende Ausgaben
- Hinweis, welche Ausgaben Klarnamen enthalten
- fehlende Pflichtfelder

Der Abschluss erzeugt atomar die neue Dokumentationsrevision samt vollständigem Snapshot. Anschließend werden die ausgewählten Ausgaben unabhängig gerendert und gespeichert. Fehler sind wiederholbar und öffnen die Dokumentation nicht erneut.

## 14. Mapping des vorhandenen Papierbogens

| Papierbogen | Werkblatt V1 | Zielausgabe |
|---|---|---|
| Zircula-Banner | Organisationsasset aus Vorlage; konkrete Datei noch offen | konfigurierter Kopf-/Logobereich |
| Titel „Teilnahme- & Auswertungsbogen …“ | Ausgabebezeichnung plus Projekt-/Programmtitel | Teilnahmeliste beziehungsweise Abschlussdokument |
| Workshoptitel | `Workshop.title` | beide |
| Name, Vorname | vorhandener Teilnehmer-Anzeigename; keine erzwungene Aufspaltung | Teilnahmeliste, optional Abschluss |
| Unterschrift | leeres Druckfeld; keine digitale Speicherung | nur Teilnahmeliste |
| Teilnahmebestätigungstext | konfigurierbarer Listentext; für die erste Vorlage zunächst wie im Papierbogen | Teilnahmeliste |
| Anzahl Teilnehmer:innen | berechnete Phase-2-Statistik | Abschluss |
| männlich/weiblich/divers | keine personenbezogenen Standardfelder; optionale aggregierte Ganzzahl-Zusatzfelder, gegebenenfalls zusätzlich „keine Angabe“ | nur konfigurierte Vorlagen |
| durchführende Person | `Facilitator` | Abschluss; optional Teilnahmeliste |
| Unterschrift der Durchführung | nicht digital erfasst; optional leeres Druckfeld nur bei ausdrücklicher Vorlagenanforderung | Teilnahmeliste |
| „Bremerhaven, den“ | `Workshop.location` und `starts_at`; fehlender Ort wird vor Ausgabe geklärt | beide |
| Bestätigung Zircula | entfällt | keine Ausgabe |
| Workshopauswertung | `Documentation.report` | Abschluss |
| Förderlogos | ausgewählte konkrete Asset-Versionen nach Rollen und Reihenfolge | konfigurierter Logo-/Förderbereich |

## 15. Vorschlag für das Abschlussdokument

Das neue Abschlussdokument ist kein digital nachgebautes Papierformular, sondern eine lesbare A4-Dokumentation:

1. **Kopf:** Werkblatt-Dokumentkennzeichnung, Organisationslogo, Projekt-/Programmtitel und optionaler Untertitel.
2. **Workshop:** Titel, Datum, Uhrzeit, Ort, Quelle nicht sichtbar, interne Referenz nur falls fachlich erforderlich.
3. **Ergebnisübersicht:** angemeldet, anwesende Anmeldungen, No-Shows, spontan, tatsächlich teilgenommen.
4. **Teilnehmende:** nur wenn die Ausgabe Klarnamen vorsieht; ausschließlich tatsächlich anwesende Personen.
5. **Durchführung:** Durchführende und „wie geplant durchgeführt“.
6. **Zusatzangaben:** freigegebene Custom Fields; aggregierte Zahlen als kompakte Statistik.
7. **Auswertung:** Bericht/Feedback mit flexiblem Seitenumbruch.
8. **Nachweis:** Revisionsnummer, Finalisierungszeitpunkt und finalisierende Person; keine zusätzliche Unterschrift.
9. **Logo-/Förderbereich:** ausgewählte Assets in festem, ruhigem Raster nach konfigurierter Reihenfolge und Rolle; optionale Fördertexte.

Das Layout wächst bei langen Inhalten auf mehrere Seiten. Logos werden proportional innerhalb definierter Flächen skaliert, niemals verzerrt oder automatisch beschnitten.

## 16. Vorschlag für die Teilnahmeliste

Die optionale Teilnahmeliste ist eine eigenständige A4-Ausgabe für den Papierworkflow:

- Organisations-/Projektkopf gemäß Vorlage
- Workshoptitel, Datum und Ort
- kurzer freigegebener Teilnahme-/Datenschutzhinweis
- vorausgefüllte Namen importierter Anmeldungen
- zusätzliche leere Zeilen für spontane Teilnehmende
- optionale Unterschriftsspalte
- bei Bedarf Durchführende mit leerem Unterschriftsfeld
- Logo-/Förderbereich
- Seitenzahl und Workshopkennung auf Folgeseiten

Die Zahl leerer Zeilen wird als kleine, feste V1-Option angeboten, beispielsweise 0, 5 oder 10. Keine digitale Unterschrift und kein automatisches Einscannen.

## 17. Namen und anonymisierte Ausgaben

Datensparsamer Default für neue Vorlagen ist `include_participant_names = false`. Die erste Zircula-Fördervorlage weicht davon bewusst ab und gibt Klarnamen im Abschlussdokument aus, weil die Fördergeber diesen Nachweis benötigen.

Bei aktivierten Namen erscheinen ausschließlich:

- anwesende importierte Registrierungen
- anwesende spontane Teilnehmende

No-Shows werden nur gezählt und nicht namentlich als tatsächliche Teilnehmende ausgegeben. Die Teilnahmeliste vor dem Workshop darf angemeldete Namen enthalten, weil sie gerade der Anwesenheitsfeststellung dient.

Die anonymisierte Ausgabe erzwingt serverseitig den Ausschluss von Namen und personenbezogenen, nicht dafür freigegebenen Zusatzfeldern. Dateinamen und Metadaten dürfen ebenfalls keine Teilnehmernamen enthalten.

## 18. Logo-/Förderbereich

V1 verwendet je Ausgabe auswählbare definierte Zonen statt freier Pixelpositionierung:

- Organisationslogo im Kopf
- Projekt-/Programmasset optional im Kopf oder Projektblock
- Förderer/Auftraggeber/sonstige Assets im Logo-Footer

Die Organisation wählt für jedes Logo Zone und Reihenfolge. Die Rolle beschreibt die fachliche Bedeutung, erzwingt aber keine namensbezogene Sonderlogik. Für Logo-Zonen kann optional die Beschriftung „Gefördert durch“ aktiviert werden.

Für viele Logos wird ein festes Raster über mehrere Zeilen verwendet. Mindestgröße und verfügbare Fläche werden vor Aktivierung geprüft; Werkblatt warnt bei zu vielen Logos, statt sie unleserlich klein zu rendern.

## 19. Verhalten bei aktualisierten und deaktivierten Assets

- Neue Vorlage: verwendet standardmäßig die aktuelle aktive Asset-Version.
- Bestehender Vorlagenstand: behält seine konkrete Asset-Version.
- Neue Asset-Version: ändert weder Vorlagenstände noch Dokumente automatisch.
- Vorlage bearbeiten: bietet die aktuelle Asset-Version an und zeigt, wenn die bisherige nicht mehr aktuell ist.
- Asset deaktivieren: verhindert neue Auswahl, zerstört aber keine bestehende Referenz.
- Historisch verwendete Version: bleibt privat gespeichert und renderbar.
- Fehlende oder beschädigte historische Datei: ist ein Integritätsfehler, kein Anlass, stillschweigend eine neue Version einzusetzen.

## 20. Tenant-Isolation

Alle Listen, Detailzugriffe, Form-Choices, Uploads, Preview-, Download- und Renderingzugriffe verwenden `(organization_id, object_id)`.

Besonders zu testen sind:

- fremde Asset-ID in Preview- und Download-URL
- fremde Asset-Version in einer Vorlagenanfrage
- manipulierte Template-, Template-Version- oder Output-ID
- fremde Custom-Field-ID oder `stable_key`
- fremde Workshop-ID bei Vorlagenzuordnung
- fremde Dokumentrevision beim Rendering oder Download
- Cache-Keys ohne Tenantanteil
- Storage-Key-Manipulation

Storage-Keys stammen ausschließlich aus serverseitig erzeugten UUIDs und werden nie aus Anzeigenamen oder Dateinamen gebildet.

## 21. Security-Tests für Uploads und Assets

V1 benötigt mindestens Tests für:

- gültiges PNG und gültiges einfaches SVG
- falsche Dateiendung versus tatsächlicher Typ
- falscher deklarierter MIME-Typ
- zu große Bytes, Kantenlänge oder Pixelzahl
- beschädigtes und stark komprimiertes PNG
- SVG mit `script`, Event-Handler, `foreignObject`, DTD, Entity und XXE-Versuch
- SVG mit externer HTTP-/Datei-URL, Remote-Schrift, `@import` oder nicht erlaubtem `url(...)`
- SVG-/XML-Bomben und Parserlimits
- fehlgeschlagene sichere Rendition ohne Anlage einer aktiven Asset-Version
- `nosniff`, sichere Content-Disposition und kein direkter Original-SVG-Aufruf
- Cross-Tenant Preview, Download, Auswahl und Versionierung
- Organization Admin versus Workshop User bei Schreiboperationen
- historische Asset-Version trotz Deaktivierung verfügbar
- neue Version überschreibt weder Bytes noch Hash der alten Version
- Snapshot referenziert exakt die beim Abschluss gewählte Version
- anonymisierte Ausgabe enthält weder Namen im Inhalt noch in Metadaten/Dateinamen

Zusätzlich bleiben die bestehenden Tenant-, Revisions- und Concurrency-Tests Release-Gates.

## 22. Analyse der bereitgestellten Dateien

Die Dateien wurden ausschließlich analysiert, nicht verändert oder als offiziell ausgewählt.

| Datei | Technische Einordnung | Status |
|---|---|---|
| `ZIRCULA_Logo_210823_schwarz.svg` | echtes skalierbares SVG mit ViewBox; technisch sehr gute Grundlage | für die erste Vorlage als Organisationslogo vorgesehen; keine weiteren Kontaktdaten erforderlich |
| `FHB_Senatorin_fu…r_UKW_lang.png` | 3000 x 867, RGBA; Inhalt innerhalb großer transparenter Außenränder | von FHB freigegeben und für die erste Vorlage gewählt; keine automatische Beschneidung |
| `FHB_Senatorin-fuer-UKW_lang.jpg` | 2450 x 407, ohne Transparenz, weißer Hintergrund | JPEG in vorgeschlagenem V1-Upload nicht unterstützt; PNG-Kandidat vorhanden |
| `Logo-Klimaschutz-Alltag-Icons.png` | 3544 x 2599, RGBA, großformatiges Projekt-/Programmmotiv | optional; konkrete Verwendung offen |
| `Dieckell…preview-3.png` | 912 x 273, RGBA, transparente Außenränder | von Dieckell freigegeben und für die erste Vorlage gewählt; keine automatische Beschneidung |
| `Dieckell-Stiftung-Logo.png` | 562 x 188, RGBA, alternative Gestaltung | Freigabestatus offen |

Die vorhandene PDF-Vorlage ist eine einseitige A4-Datei ohne interaktive Formularfelder. Sie verbindet Teilnahmeliste, Unterschriften, Statistik, Durchführungsbestätigung und Auswertung. Das neue Konzept trennt diese Zwecke in wiederverwendbare Ausgaben.

## 23. Festlegungen für die erste Zircula-Vorlage

- Ausgaben: Abschlussdokument und druckbare Teilnahmeliste
- Klarnamen: tatsächlich anwesende Personen erscheinen im Abschlussdokument, da die Fördergeber den Nachweis benötigen
- Teilnahmeliste: Namen plus Unterschriftsfelder für Teilnehmende; kein zusätzliches Unterschriftsfeld für Durchführende
- Teilnahmetext: initial „Mit dem Eintrag auf dieser Liste bestätige ich die Teilnahme an oben aufgeführtem Workshop.“; innerhalb der Vorlage anpassbar
- Fördertext: zunächst kein verpflichtender Freitext; Logo-Zonen können optional mit „Gefördert durch“ beschriftet werden
- Zusatzstatistik: freiwillige aggregierte Ganzzahlfelder `männlich`, `weiblich`, `divers` und `keine Angabe`, ohne Zuordnung zu einzelnen Personen
- Organisationsprofil: für interne Zircula-Bögen zunächst keine umfangreichen Kontaktdaten; spätere Organisationen können diese im eigenen Profil pflegen
- Dieckell: `Dieckell_Sitfung_Logo_Final_-_Marc_Bergman-removebg-preview-3.png`, Rolle Förderer, freigegeben
- FHB/Senatorin: transparentes `FHB_Senatorin_fu…r_UKW_lang.png`, Rolle Förderer, freigegeben
- Klimaschutz im Alltag: Rolle Projekt/Programm, optional auswählbar
- Zircula e.V.: Rolle durchführende Organisation
- Logo-Zone und Reihenfolge werden in der Dokumentvorlage gewählt und nicht global festgelegt

Konkrete spätere Förderpflichttexte oder weitere Anforderungen können als Vorlagenkonfiguration ergänzt werden. Für die generische V1-Architektur und die erste Vorlage bestehen derzeit keine weiteren fachlichen Blocker.

## 24. V1-Abgrenzung und Freigabe-Gate

Phase 3b soll nach Freigabe dieses Konzepts ausschließlich die hier beschriebene pragmatische V1 umsetzen: Asset-Bibliothek, sichere Uploads, versionierte Assets, wiederverwendbare versionierte Dokumentvorlagen, feste Ausgabearten, einfache Zusatzfelder, Workshopzuordnung, Snapshots, PDF-Rendering und den bereits getrennt geplanten Storage-Prozess.

Nicht Teil von V1 sind freier PDF-Designer, Drag-and-Drop-Layout, beliebige Positionierung, Formeln, Skripte, bedingte Feldlogik, digitale Signaturen, Scanablage, universeller No-Code-Formbuilder, organisationsübergreifende Asset-Nutzung oder vollständiges White-Labeling.

Vor ausdrücklicher Freigabe dieses Phase-3a-Vorschlags werden keine Modelle, Migrationen, Uploads, PDF-Templates oder Storage-Workflows implementiert.
