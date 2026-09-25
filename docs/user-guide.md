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

Zusätzlich kann die persönliche Standardansicht der Workshops gewählt werden.
Ohne abweichende Auswahl öffnet Werkblatt den Kalender. Der Wechsel zwischen
Kalender und Liste ist auch direkt in der Workshopübersicht möglich und wird
für das eigene Benutzerkonto gespeichert.

Werkblatt V1 ist derzeit vollständig auf Deutsch verfügbar. Weitere Sprachen
werden erst auswählbar, wenn ihre Übersetzung vollständig bereitsteht.

## Workshops und Dokumentationen

Mit „Workshop anlegen“ können Workshop User, Editor und Organization Admins
Veranstaltungen erfassen, die nicht aus Pretix stammen. Titel und Beginn sind
Pflicht; Ende und Ort können ergänzt werden. Werkblatt öffnet anschließend
direkt die neue Dokumentation. Manuell angelegte Workshops lassen sich über
„Workshop bearbeiten“ korrigieren. Pretix-Workshops werden weiterhin durch die
Integration gepflegt und können dort nicht bearbeitet werden.

Ein Workshop führt zur zugehörigen Dokumentation. Dort können berechtigte
Nutzer der eigenen Organisation Entwurfsdaten, Teilnehmende, Anwesenheiten und
weitere vorlagenabhängige Angaben bearbeiten.

Aus Pretix übernommene Anmeldungen sind als „Pretix“ gekennzeichnet und können
nicht versehentlich entfernt oder einer anderen Teilnahmeart zugeordnet werden.
Manuell ergänzte Personen können als „Spontan teilgenommen“ oder „Außerhalb von
Pretix angemeldet“ erfasst und später korrigiert werden. Manuelle Anmeldungen
zählen in Statistik und Anwesenheitsquote als angemeldet; spontane Teilnahmen
werden weiterhin getrennt ausgewiesen.

Vor dem Abschluss wird eine Dokumentvorlage zugeordnet. Ihre Zusatzfelder
erscheinen unmittelbar nach der Auswahl; bereits eingegebene Teilnehmende,
Durchführende und Berichtstexte bleiben erhalten. Bei einem neueren
Vorlagenstand weist Werkblatt darauf hin und bietet dessen bewusste Übernahme
an. Beim Finalisieren
entsteht ein unveränderlicher Snapshot. Eine abgeschlossene Dokumentation kann
erneut geöffnet, korrigiert und als neue Revision abgeschlossen werden; ältere
Revisionen bleiben erhalten.

Die Workshopliste kann nach Titel oder Ort, Zeitraum, Sichtbarkeit und
Bearbeitungsstand gefiltert werden. Längere Listen werden auf mehrere Seiten
verteilt. Editor und Organization Admin können Workshops aus der täglichen
Ansicht ausblenden und über den Filter „Ausgeblendet“ wieder einblenden. Das
Ausblenden löscht weder Workshop noch Dokumentation und hebt eine bestehende
Dokumentationspflicht nicht auf.

Über „Kalender“ wechselt die Workshopübersicht in eine Monatsansicht. Ein Klick
auf einen dokumentationspflichtigen Workshop öffnet direkt seine Dokumentation.
Die Zustände offen, Entwurf, abgeschlossen, nicht erforderlich und abgesagt
bleiben sichtbar; auf kleinen Bildschirmen wird der Monat als kompakte Agenda
dargestellt.

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

Der regelmäßige Pretix-Abgleich markiert abgesagte, nicht mehr öffentliche oder
entfernte Termine als „Abgesagt“, statt sie zu löschen. Solche Workshops können
nicht dokumentiert werden und fließen nicht in Durchführungs- oder
Teilnahmestatistiken ein; vorhandene abgeschlossene Revisionen bleiben erhalten.
Wird ein Termin in Pretix wieder aktiviert, erscheint er nach dem nächsten
Abgleich erneut als aktiv.

Unter „Verwaltung → Pretix-Erstellung“ verwalten Organization Admins die
Standards für den vereinfachten Erstellungsablauf. Ein Standard verweist auf
eine dauerhaft inaktive und nicht öffentlich gelistete Pretix-Vorlage. Die
Felder für Standard- und Kinderticket erwarten deren interne technische Namen;
die öffentlich sichtbaren Ticketnamen werden dadurch nicht verändert.

Mit „Vorlage prüfen“ liest Werkblatt ausschließlich Eventstatus, Produkte und
Kontingente aus Pretix. Die Prüfung erzeugt oder verändert keine Veranstaltung
und greift nicht auf Bestellungen oder Teilnehmerdaten zu. Sie bestätigt nur,
dass die Vorlage verborgen ist, beide Produkte eindeutig zugeordnet sind und
ein gemeinsames Kapazitätskontingent besitzen.

Optionale Fördertexte werden auf derselben Verwaltungsseite gepflegt. Ein
später erstellter Workshop erhält eine Kopie des ausgewählten Textstands, damit
nachträgliche Änderungen vorhandene Erstellungsvorgänge nicht verändern.

Werkblatt bildet bewusst nur den einfachen Standardfall ab. Verpflichtende
Fragen, zusätzliche Ticketarten oder Varianten, besondere E-Mail-Texte und
weitere Pretix-Funktionen werden weiterhin in der Pretix-Verwaltung gepflegt.
Der Verwaltungsbereich enthält dafür einen direkten Link zum `/control`-Bereich
der konfigurierten Pretix-Instanz.

Mit „Workshop mit Anmeldung“ öffnen Workshop User, Editor und Organization
Admins den vereinfachten Erstellungsassistenten. Nach Auswahl des Standards
werden Titel, Beginn, optionales Ende, Ort, Beschreibung, optionaler
Fördertext, Kapazität und Kinderanmeldung erfasst. Der automatisch erzeugte
Pretix-Slug erhält eine laufende Nummer.

Vor dem externen Schreibzugriff zeigt Werkblatt eine vollständige
Zusammenfassung. Erst „In Pretix erstellen und veröffentlichen“ klont die
verborgene Vorlage, setzt Beschreibung, Fördertext, Kapazität und
Kinderprodukt, überprüft das Ergebnis und veröffentlicht die Veranstaltung.
Anschließend steht der Workshop unmittelbar zur Dokumentation bereit; der
regelmäßige Sync ergänzt später eingehende Anmeldungen.

Schlägt der Ablauf nach einem externen Teilschritt fehl, führt Werkblatt keine
automatische Wiederholung aus. Dadurch wird kein zweites Event angelegt. Der
Vorgang wird technisch markiert und muss zunächst in Pretix kontrolliert
werden.

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
Auswertung kann ohne Klarnamen als CSV exportiert werden. Abgesagte Workshops
werden separat ausgewiesen und nicht in diese Kennzahlen eingerechnet.

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
Zusatzfelder lassen sich im Vorlageneditor mit „+ Weiteres Zusatzfeld“ in der
benötigten Anzahl ergänzen und einzeln entfernen.

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
