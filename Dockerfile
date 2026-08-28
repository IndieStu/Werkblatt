FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM python:3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp/werkblatt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdk-pixbuf-2.0-0 libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libharfbuzz-subset0 shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin werkblatt
WORKDIR /app
COPY --from=builder --chown=werkblatt:werkblatt /build/.venv /app/.venv
COPY --chown=werkblatt:werkblatt manage.py ./
COPY --chown=werkblatt:werkblatt config ./config
COPY --chown=werkblatt:werkblatt templates ./templates
COPY --chown=werkblatt:werkblatt static ./static
RUN mkdir -p /app/var/media /tmp/werkblatt \
    && chown -R werkblatt:werkblatt /app/var /tmp/werkblatt
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=2", "--access-logfile=-"]
