# Werkblatt – Nutzungsanleitung

Diese Anleitung beschreibt den aktuellen Funktionsstand von Werkblatt. Die
Oberfläche kann sich während der Pilotphase noch weiterentwickeln.

## Anmeldung und Navigation

Die Anmeldung erfolgt über den vom Betreiber eingerichteten OIDC-Dienst. Nach
der Anmeldung zeigt „Workshops“ alle Workshops der eigenen Organisation.
Organisationsübergreifende Inhalte sind nicht zugänglich.

„Einstellungen“ enthält ausschließlich persönliche Präferenzen. Editor sehen
zusätzlich „Redaktion“ für Dokumentvorlagen und dokumentbezogene Assets.
Organization Admins sehen „Verwaltung“ einschließlich organisationsweiter
Konfiguration.

„Statistik“ steht allen drei fachlichen Rollen zur Verfügung und zeigt
ausschließlich aggregierte Werte der eigenen Organisation. Teilnehmer:innennamen
werden weder dort noch im Statistik-CSV ausgegeben.

## Persönliche Einstellungen

Unter „Einstellungen“ kann das Erscheinungsbild gewählt werden:

- **Hell** verwendet die helle Werkblatt-Darstellung.
- **Dunkel** verwendet die dunkle Ableitung des Werkblatt Corporate Designs.
- **Systemeinstellung** folgt der Hell-/Dunkel-Einstellung des Browsers oder
  Betriebssystems.

Werkblatt V1 ist derzeit vollständig auf Deutsch verfügbar. Weitere Sprachen
werden erst auswählbar, wenn ihre Übersetzung vollständig bereitsteht.

## Workshops und Dokumentationen

Ein Workshop führt zur zugehörigen Dokumentation. Dort können berechtigte
Nutzer der eigenen Organisation Entwurfsdaten, Teilnehmende, Anwesenheiten und
weitere vorlagenabhängige Angaben bearbeiten.

Vor dem Abschluss wird eine Dokumentvorlage zugeordnet. Beim Finalisieren
entsteht ein unveränderlicher Snapshot. Eine abgeschlossene Dokumentation kann
erneut geöffnet, korrigiert und als neue Revision abgeschlossen werden; ältere
Revisionen bleiben erhalten.

Die Workshopliste kann nach Titel oder Ort, Zeitraum, Sichtbarkeit und
Bearbeitungsstand gefiltert werden. Längere Listen werden auf mehrere Seiten
verteilt. Editor und Organization Admin können Workshops aus der täglichen
Ansicht ausblenden und über den Filter „Ausgeblendet“ wieder einblenden. Das
Ausblenden löscht weder Workshop noch Dokumentation und hebt eine bestehende
Dokumentationspflicht nicht auf.

Nur Organization Admins dürfen für einen einzelnen Workshop „Keine
Dokumentation erforderlich“ festlegen. Dafür ist eine Begründung Pflicht; Person
und Zeitpunkt werden gespeichert. Solange die Entscheidung gilt, kann keine
Dokumentation für diesen Workshop geöffnet werden.

Unter „Verwaltung → Pretix-Veranstaltungsregeln“ steuern Organization Admins
Import und Dokumentationspflicht anhand des stabilen Pretix-Event-Slugs. Bei
einer Veranstaltungsreihe gilt eine Regel automatisch für alle vorhandenen und
zukünftigen Termine. Eine Einzelentscheidung am Workshop übersteuert die
Reihenregel. Neue Veranstaltungen bleiben ohne Regel standardmäßig
dokumentationspflichtig.

## Statistik

Die Statistik kann nach Workshopdatum eingegrenzt werden. Pro Dokumentation
wird ausschließlich die neueste abgeschlossene Revision berücksichtigt, damit
Korrekturen und frühere Revisionen nicht doppelt gezählt werden. Wird eine
abgeschlossene Dokumentation erneut zur Korrektur geöffnet, bleiben ihre zuletzt
abgeschlossenen Werte sichtbar und werden als „Korrektur ausstehend“ markiert.

Neben Workshops, Anmeldungen, Teilnahmen, No-Shows und spontanen Teilnahmen
werden vorlagenspezifische Zahlenfelder mit der Darstellung „Aggregierte
Statistik“ summiert. Die Anwesenheitsquote bezieht sich nur auf angemeldete
Personen; spontane Teilnahmen werden separat ausgewiesen. Die gefilterte
Auswertung kann ohne Klarnamen als CSV exportiert werden.

## Redaktion und Organisationsverwaltung

Editor können in „Redaktion“ Dokumentvorlagen sowie Förder-, Projekt-,
Auftraggeber- und sonstige Dokumentassets verwalten. Vorhandene
Organisationslogos dürfen sie in Vorlagen auswählen, jedoch nicht verändern oder
versionieren.

Dokumentvorlagen können nach Eingabe ihres exakten Namens entfernt werden.
Werkblatt archiviert sie dabei sicher: Sie verschwinden aus neuen
Workshopzuordnungen, während frühere Vorlagenstände, Revisionen und Dokumente
erhalten bleiben. Archivierte Vorlagen werden getrennt angezeigt und können
über einen neuen Vorlagenstand reaktiviert werden.

Organization Admins besitzen dieselben redaktionellen Rechte und sehen unter
„Verwaltung“ zusätzlich das Organisationsprofil. Organisationsbranding,
Integrationen sowie Memberships und Rollen bleiben ebenfalls ausschließlich
Organization Admins vorbehalten.

Persönliche Einstellungen verändern keine dieser organisationsweiten Angaben.

## Probleme melden

Technische Fehler und nachvollziehbare Verbesserungsvorschläge können im
[öffentlichen Issue-Tracker](https://github.com/IndieStu/Werkblatt/issues)
gemeldet werden. Dabei dürfen keine personenbezogenen Teilnehmerdaten, Tokens,
Passwörter oder andere Secrets veröffentlicht werden.
