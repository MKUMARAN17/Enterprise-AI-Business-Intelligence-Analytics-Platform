"""FastAPI app factory.

Builds the app, wires CORS + the fail-closed JWT gate, and mounts the
conversation router. The compiled ``OrchestrationService`` is INJECTED (by the
prod entrypoint via the composition root, or by a test with fakes) and stashed on
``app.state`` — the factory itself never reaches out to a database or an LLM, so
it can be imported and exercised in isolation.
"""
from __future__ import annotations

from enterprise_bi.config.settings import Settings


def create_app(settings: Settings | None = None, *, service=None, validator=None):
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    from enterprise_bi.api import build_conversation_router
    from enterprise_bi.app.composition import build_validator
    from enterprise_bi.auth_dep import make_auth_dependency

    settings = settings or Settings()
    app = FastAPI(title="enterprise-ai-bi-platform", version="0.1.0", root_path=settings.root_path)

    if validator is None:
        validator = build_validator(settings)
    app.state.orchestration_service = service
    app.state.jwt_validator = validator

    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "enterprise-ai-bi-platform"}

    if validator is not None:
        auth_dep = make_auth_dependency(validator)
    else:
        async def auth_dep():  # noqa: ANN202 - fail-closed stub
            raise HTTPException(
                status_code=503,
                detail={"code": "AUTH_NOT_CONFIGURED", "message": "JWT validator not configured"},
            )

    app.include_router(build_conversation_router(auth_dep))
    return app
