FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /srv/qrguard

COPY backend/requirements-prod.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt

COPY backend ./backend
COPY training/artifacts/structural ./training/artifacts/structural
COPY training/artifacts/semantic ./training/artifacts/semantic
COPY ml_training/structural/runs/structural-2026.02/artifacts \
    ./ml_training/structural/runs/structural-2026.02/artifacts

RUN useradd --create-home --uid 10001 qrguard \
    && chown -R qrguard:qrguard /srv/qrguard
USER qrguard

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8080}"]
