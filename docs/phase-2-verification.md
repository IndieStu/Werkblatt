# Phase 2: Verifikation der Status- und Revisionsübergänge

Stand: 28. August 2026  
Ergebnis: bestanden

Vor dem Start von Phase 3 wurden die Status- und Revisionsregeln durch zusätzliche Service- und Mandantentests explizit abgesichert. Dabei wurden keine Modelle, Services oder Architekturstrukturen verändert.

## Abgesicherte Fälle

- `finalize -> reopen -> edit -> finalize` erzeugt zwei fortlaufende Revisionen.
- Ein zweites `finalize` ohne vorheriges `reopen` wird abgewiesen und erzeugt keine weitere Revision.
- `reopen` wird für einen Entwurf abgewiesen.
- `save` und `finalize` werden mit einem fremden `organization_id` abgewiesen und verändern keine Daten.
- Zwei Schreibversuche mit derselben Ausgangsversion können den neueren Stand nicht überschreiben.
- Snapshot und SHA-256-Hash einer älteren Revision bleiben nach Korrektur und erneuter Finalisierung unverändert.
- Der Versuch, eine bereits gespeicherte Revision über das Modell zu verändern, wird abgewiesen.

## Vollständiger Prüflauf

Ausgeführt im Projekt-Root mit der gebündelten Python-Laufzeit:

```text
python -m ruff check .                         All checks passed
python -m ruff format --check .                58 files already formatted
python manage.py makemigrations --check --dry-run  No changes detected
python manage.py check                         0 issues
python -m pytest -q                            18 passed in 0.54s
git diff --check                               keine Beanstandungen
```

Damit ist der ergänzende Verifikationsschritt für Phase 2 abgeschlossen. Phase 3 wurde nicht begonnen.
