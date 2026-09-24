FROM ghcr.io/astral-sh/uv:0.8.15@sha256:a5727064a0de127bdb7c9d3c1383f3a9ac307d9f2d8a391edc7896c54289ced0 AS uv

FROM python:3.13-slim@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0 AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0
ARG WERKBLATT_BUILD_VERSION=development
ARG WERKBLATT_SOURCE_CODE_URL=https://github.com/IndieStu/Werkblatt
LABEL org.opencontainers.image.title="Werkblatt" \
      org.opencontainers.image.source="${WERKBLATT_SOURCE_CODE_URL}" \
      org.opencontainers.image.revision="${WERKBLATT_BUILD_VERSION}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp/werkblatt \
    XDG_CACHE_HOME=/tmp/werkblatt/.cache \
    WERKBLATT_BUILD_VERSION="${WERKBLATT_BUILD_VERSION}" \
    WERKBLATT_SOURCE_CODE_URL="${WERKBLATT_SOURCE_CODE_URL}" \
    WERKBLATT_LICENSE_EXPRESSION="AGPL-3.0-or-later"
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
COPY --chown=root:root LICENSE NOTICE.md THIRD_PARTY_LICENSES.md BRAND_POLICY.md /usr/share/doc/werkblatt/
COPY --chown=root:root licenses /usr/share/doc/werkblatt/licenses
RUN mkdir -p /app/var/media /tmp/werkblatt \
    && chown -R werkblatt:werkblatt /app/var /tmp/werkblatt \
    && DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && chown -R werkblatt:werkblatt /app/staticfiles \
    && chmod -R u=rwX,go=rX /app/staticfiles
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=2", "--timeout=30", "--error-logfile=-", "--capture-output"]
