"""Production ASGI entrypoint.

    uvicorn enterprise_bi.app.main:app

Configures logging, builds the real OrchestrationService from Settings (the
composition root), and hands it to the app factory. A misconfiguration surfaces
as a ConfigError at import time (fail-closed) instead of a half-wired service.
"""
from __future__ import annotations

from bi_base import configure_logging

from enterprise_bi.app.composition import build_orchestration_service
from enterprise_bi.app.factory import create_app
from enterprise_bi.config.settings import Settings


def build_app():
    settings = Settings()
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)
    service = build_orchestration_service(settings)
    return create_app(settings, service=service)


app = build_app()
