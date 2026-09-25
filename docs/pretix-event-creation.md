# Pretix-Veranstaltungen aus Werkblatt erstellen

## Ziel und Produktgrenze

Werkblatt soll einen bewusst reduzierten Assistenten für wiederkehrende,
kostenfreie Workshops anbieten. Es ersetzt weder die Pretix-Verwaltung noch
bildet es deren vollständige Event-, Produkt- oder Steuerkonfiguration nach.
Stattdessen klont Werkblatt eine von der Organisation in Pretix gepflegte
Veranstaltungsvorlage und ändert ausschließlich freigegebene Werte.

Der Assistent soll zunächst Titel, Beginn, Ende, Ort, Beschreibung,
Fördertext, Gesamtkapazität und die Freigabe der Kinderanmeldung erfassen.
Steuern, Zahlungsarten, Ticketfragen, E-Mail-Texte und Benachrichtigungen
bleiben Teil der Pretix-Vorlage und werden nicht als Werkblatt-Felder
dupliziert.

## Organisationsbezogene Erstellungsstandards

Ein späteres Modell `PretixCreationPreset` gehört fachlich zur bestehenden
Workshop-/Pretix-Integration und ist immer an eine Organisation gebunden. Ein
Preset enthält keine Zugangsdaten, sondern insbesondere:

- eine verständliche Bezeichnung;
- den Slug des Pretix-Vorlagen-Events;
- stabile interne Kennungen für Standard- und Kinderprodukt;
- auswählbare, ebenfalls organisationsbezogene Fördertexte;
- Aktivstatus und optional administrative Standardwerte.

Der aktuelle Zircula-Pilot verwendet weiterhin die per Deployment gesetzte
Pretix-Verbindung. Diese temporäre Single-Tenant-Konfiguration ist keine
langfristige Hosted-Architektur. Vor einer zweiten Organisation müssen
Verbindungs- und Secret-Zuordnung tenantgebunden umgesetzt werden.

## Anforderungen an eine Pretix-Vorlage

Das Vorlagen-Event bleibt dauerhaft `live = false` und `is_public = false`.
Sein Datum darf vergangen sein, weil jedes geklonte Event eigene Zeitangaben
erhält. Ein weit in der Zukunft liegendes Scheindatum ist nicht erforderlich.
Die Vorlage wird durch eine Pretix-Veranstaltungsregel vom regulären
Werkblatt-Import ausgeschlossen.

Sichtbare, übersetzbare Produktnamen sind keine stabilen technischen
Kennungen. Standard- und Kinderprodukt benötigen deshalb eindeutige interne
Namen. Für Zircula sind vorgesehen:

- `werkblatt_standard`;
- `werkblatt_child`;
- optional später `werkblatt_catering`.

Vor dem ersten echten Schreibtest prüft Werkblatt lesend, ob genau ein Produkt
je interner Kennung und genau ein gemeinsames Kapazitätskontingent existieren.
Bei einer fehlenden oder mehrdeutigen Zuordnung findet kein POST statt.

## Automatische Slugs

Nutzende geben keinen Pretix-Slug ein. Werkblatt normalisiert den Titel zu
einem ASCII-Basiswert und ergänzt immer eine laufende Zahl, beispielsweise
`klimawerkstatt-gropelingen-1`. Für einen weiteren Workshop mit demselben
Basistitel folgt `klimawerkstatt-gropelingen-2`.

Die spätere persistente Erstellungsanforderung reserviert den Slug
serverseitig. Bei der Vergabe werden sowohl die organisationsbezogene lokale
Historie als auch vorhandene Pretix-Events berücksichtigt. Ein Konflikt wird
nicht durch Überschreiben gelöst. Stattdessen ermittelt Werkblatt kontrolliert
die nächste Nummer. Ein einmal erfolgreich verwendeter Slug bleibt im
Vorgangsprotokoll erhalten, auch wenn das externe Event später gelöscht wird.

## Sicherer Erstellungsablauf

1. Berechtigung und aktive Organisation serverseitig prüfen.
2. organisationsbezogenes Preset und Fördertext laden.
3. Eingaben validieren und einen Slug reservieren.
4. Pretix-Vorlage vor dem Schreiben strukturell validieren.
5. Event mit `live = false` und `is_public = false` klonen.
6. Kinderprodukt aktivieren oder deaktivieren.
7. gemeinsames Kontingent auf die gewünschte Kapazität setzen.
8. Beschreibung und ausgewählten Fördertext über explizit freigegebene
   Pretix-Einstellungen aktualisieren.
9. Event erneut aus Pretix lesen und den sicheren Zustand prüfen.
10. Erstellungsstatus und externe Referenz lokal speichern.
11. Event erst über eine getrennte, bewusste Aktion veröffentlichen.

Während externer HTTP-Aufrufe bleibt keine lang laufende Datenbanktransaktion
offen. Wiederholte Formularübermittlung verwendet dieselbe lokale
Erstellungsanforderung und darf kein zweites Event erzeugen. Ein Abbruch nach
dem Klonen wird als wiederaufnehmbarer Fehler protokolliert; das verborgene
Pretix-Event wird nicht automatisch destruktiv gelöscht.

## Berechtigungen

Die Verwaltung von Presets, Fördertexten, Produktzuordnungen und
Pretix-Verbindungen bleibt Organization Admins vorbehalten. Vor Einführung der
Bedienoberfläche wird separat festgelegt, ob Workshop User Events unmittelbar
erstellen dürfen oder ob diese Fähigkeit zunächst Editor und Organization
Admin vorbehalten bleibt. Veröffentlichung ist in jedem Fall eine eigene
Capability und kein Nebeneffekt des Erstellens.

## Umsetzungsstufen

1. **Adapter-Grundbau:** begrenzte POST-/PATCH-Methoden, Vorlagenprüfung,
   verborgenes Klonen, Kapazität, Kinderprodukt, Slug-Helfer und Mocktests.
2. **Persistente Fachlogik:** organisationsbezogene Presets, Fördertexte,
   idempotente Erstellungsanforderungen und Auditstatus.
3. **Administrationsoberfläche:** Presets und Fördertexte konfigurieren sowie
   Verbindung lesend prüfen.
4. **Erstellungsassistent:** reduzierte Eingabemaske, Vorschau und verborgene
   Erstellung.
5. **Echter Pretix-Test:** ausschließlich synthetisches Event, Prüfung im
   Pretix-Backend und kontrollierte Bereinigung.
6. **Veröffentlichung:** getrennte Freigabeaktion erst nach weiterem
   Security- und Berechtigungsreview.
