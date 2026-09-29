# Offene Werkstätten

Offene Werkstätten sind eine eigenständige, organisationsgebundene
Besuchserfassung innerhalb der bestehenden Workshop-Domäne. Sie sind keine
verkürzte Dokumentation und erzeugen weder Revisionen noch Snapshots, PDFs oder
WebDAV-Dateien.

## Fachmodell

`OpenWorkshopSeries` beschreibt ein wiederkehrendes Angebot mit Name, Ort,
menschenlesbarer Terminbeschreibung und Aktivstatus. Eine Deaktivierung
verhindert neue Erfassungen, erhält aber alle historischen Werte.

`OpenWorkshopAttendance` beschreibt genau einen tatsächlich stattgefundenen
Termin einer Reihe. Pro Organisation, Reihe und Datum ist höchstens ein Eintrag
zulässig. Gespeichert werden ausschließlich:

- Datum und Reihe;
- Teilnehmende insgesamt;
- weiblich, männlich, divers und keine Angabe;
- optionale interne Notiz;
- erfassender User und technische Zeitstempel.

Die Geschlechterwerte müssen in Summe der Gesamtzahl entsprechen. Es werden
keine Namen oder sonstigen personenbezogenen Teilnehmerdaten erhoben.

## Rollen

- Workshop User, Editor und Organization Admin dürfen Termine innerhalb ihrer
  aktiven Organisation erfassen und korrigieren.
- Nur Editor und Organization Admin dürfen Reihen anlegen oder konfigurieren.
- Fremde Reihen und Einträge werden sowohl durch tenantgebundene Querysets als
  auch durch serverseitige Validierung abgewiesen.

## Statistik

Die getrennte Auswertung kann nach Zeitraum und Reihe gefiltert werden. Sie
enthält Anzahl der Termine, Gesamtteilnahmen, Durchschnitt pro Termin,
Geschlechterangaben und Summen je Reihe. Der CSV-Export enthält nur diese
aggregierten beziehungsweise terminbezogenen Werte und keine Usernamen.

## Kumulierte CSV-Ausgabe

Der CSV-Export enthält zusätzlich zu den bisherigen terminbezogenen Zeilen eine
kumulierte Auswertung für den ausgewählten Zeitraum enthalten:

- je Veranstaltungsreihe den Namen, die Gesamtzahl ihrer Termine und die Summe
  ihrer Teilnehmenden;
- über alle im Filter enthaltenen Reihen hinweg eine Gesamtsumme der Termine
  und Teilnehmenden.

Der bestehende Zeitraum- und Reihenfilter gilt auch für diese Summen. Die
kumulierte Ausgabe ersetzt den Detailbereich nicht. Sie bleibt vollständig
tenantgebunden und enthält keine Namen von Teilnehmenden oder erfassenden
Usern.
