# Organisationsbezogene Statistik

Werkblatt stellt angemeldeten Workshop Usern, Editoren und Organization Admins
eine tenantgebundene Statistikansicht unter `/documentation/statistics/` bereit.
Sie enthält keine Teilnehmer:innen- oder Benutzernamen. Der CSV-Export bildet
die aggregierten Werte ab und ergänzt für Verwendungsnachweise Workshopnamen
mit der jeweiligen aggregierten Teilnahmezahl.

## Datenbasis und Revisionen

Der Zeitraum bezieht sich auf das Datum des Workshops. Pro Dokumentation wird
höchstens die neueste abgeschlossene, unveränderliche Revision ausgewertet.
Ältere Revisionen werden niemals addiert. Ist eine Dokumentation zur Korrektur
wieder geöffnet, bleibt die letzte abgeschlossene Revision die statistische
Grundlage; die Ansicht weist diesen Zustand zusätzlich als „Korrektur
ausstehend“ aus. Workshops ohne abgeschlossene Revision fließen nur in die
Zahlen „Workshops“ und „Ohne Abschluss“ ein. Workshops mit der begründeten
Entscheidung „Keine Dokumentation erforderlich“ werden separat gezählt und
nicht als fehlender Abschluss behandelt.

## Kennzahlen

- Workshops im gewählten Zeitraum
- Workshops mit beziehungsweise ohne Abschluss
- Dokumentationen mit geöffneter Korrektur
- angemeldete und davon anwesende Personen
- No-Shows
- spontane Teilnahmen
- Teilnahmen insgesamt
- Anwesenheitsquote der angemeldeten Personen
- numerische Custom Fields mit `presentation = aggregate_statistic`

Die Anwesenheitsquote verwendet `present_registered / registered`. Spontane
Teilnahmen stehen separat und können die Quote daher nicht über 100 Prozent
heben. Aggregierte Custom Fields werden anhand ihres im Snapshot eingefrorenen
Labels summiert und zusätzlich nach Projekt und Dokumentvorlage gruppiert.

Die Auswertung kann optional nach einer organisationsbezogenen Dokumentvorlage
gefiltert werden. Als Projektzuordnung gilt die Vorlage, die im jeweils letzten
abgeschlossenen Revisionssnapshot eingefroren ist. Bei einer geöffneten
Korrektur bleibt damit weiterhin die letzte abgeschlossene Revision relevant.
In diesem Filtermodus beziehen sich Workshopanzahl und Summen ausschließlich
auf die abgeschlossenen Dokumentationen dieser Vorlage.

## Datenschutz und Tenant-Isolation

Alle Abfragen beginnen mit dem serverseitig validierten Organisationskontext.
Requestparameter können keine Organisation auswählen. Auch die
Dokumentvorlagenauswahl ist auf die aktive Organisation begrenzt. Der
CSV-Export enthält zwar die für Verwendungsnachweise benötigten Workshoptitel,
aber weder Teilnehmendennamen noch Benutzerkennungen oder Freitextberichte.
Cross-Tenant- und Revisionsregeln sind automatisiert getestet.

Die Statistik ist eine operative Auswertung und kein behördliches oder
revisionspflichtiges Fachverfahren. Ihre Nachvollziehbarkeit entsteht aus den
unveränderlichen Dokumentationsrevisionen, nicht aus einem separaten
Statistikdatenbestand.

## Workshopbezogene CSV-Ausgabe

Für Verwendungsnachweise enthält der CSV-Export zusätzlich zur bestehenden
Gesamtauswertung eine workshopbezogene Zusammenfassung. Innerhalb des
gewählten Zeitraums weist sie aus:

- die Gesamtzahl der berücksichtigten Workshops;
- je Workshop den Workshopnamen und die aggregierte Zahl der Teilnehmenden;
- die optionale Projektauswahl anhand der verwendeten Dokumentvorlage.

Bis ein eigenständiges Projektmodell fachlich erforderlich wird, gilt die bei
der maßgeblichen abgeschlossenen Revision eingefrorene Dokumentvorlage als
Projektzuordnung. Teilnehmer:innennamen, Freitexte und andere personenbezogene
Angaben bleiben vom Export ausgeschlossen.
