FROM python:3.13-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 werkblatt
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=werkblatt:werkblatt manage.py ./
COPY --chown=werkblatt:werkblatt config ./config
COPY --chown=werkblatt:werkblatt templates ./templates
COPY --chown=werkblatt:werkblatt static ./static
USER werkblatt
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=2", "--access-logfile=-"]

