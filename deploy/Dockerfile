# Enterprise BI backend — production image.
# Multi-stage: build a wheel-installed venv, then copy into a slim runtime.
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# System deps for building crypto/mysql wheels.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ /app/backend/
RUN python -m venv /venv \
    && . /venv/bin/activate \
    && pip install --upgrade pip \
    && pip install /app/backend/packages/bi-base /app/backend/packages/bi-auth \
                   /app/backend/packages/bi-llm /app/backend/packages/bi-data \
                   /app/backend/packages/bi-guardrails /app/backend/packages/bi-sql-guard \
                   /app/backend/packages/bi-schema-rag /app/backend/packages/bi-viz \
                   /app/backend/packages/bi-reports \
    && pip install "/app/backend[llm]"

FROM python:3.11-slim AS runtime
ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=builder /venv /venv
COPY backend/ /app/backend/
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "enterprise_bi.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
