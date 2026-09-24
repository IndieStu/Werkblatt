# Zu Werkblatt beitragen

Danke für dein Interesse an Werkblatt. Änderungen sollen die vorhandenen
fachlichen Module und die konventionelle Django-/Python-Struktur erhalten.
Neue Top-Level-Verzeichnisse, generische Sammelmodule oder zusätzliche
Architekturschichten benötigen eine konkrete fachliche Begründung.

## Lizenz der Beiträge

Beiträge zum Werkblatt-Programmcode werden unter derselben Lizenz wie das
Projekt eingereicht: `AGPL-3.0-or-later` (Inbound = Outbound).

Jeder Commit benötigt eine `Signed-off-by`-Zeile entsprechend dem
[Developer Certificate of Origin 1.1](https://developercertificate.org/). Mit
dem Sign-off bestätigt die beitragende Person insbesondere, dass sie den
Beitrag selbst geschaffen hat oder zu seiner Einreichung unter der
Projektlizenz berechtigt ist. Ein Sign-off kann mit `git commit -s` erzeugt
werden. Der DCO überträgt keine Urheberrechte.

Das Werkblatt Brand System ist kein frei bearbeitbarer Beitragsbereich. Siehe
`BRAND_POLICY.md`. Änderungen an vorbehaltenen Brand-Assets werden nur nach
ausdrücklicher Freigabe durch Timo Hecken angenommen.

## Vor einem Pull Request

```bash
uv sync --frozen --all-extras
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run pytest -q
uv run pip-audit
```

Bei neuen oder aktualisierten Abhängigkeiten gilt zusätzlich
`docs/dependency-policy.md`. Änderungen dürfen keine Secrets, produktiven
Personendaten oder organisationsbezogenen Runtime-Assets enthalten.
