"""Conversation API routes.

`POST /api/v1/ask` is the single natural-language entrypoint. Auth is enforced at
this boundary (fork-style): the injected ``auth_dep`` validates the bearer token
and yields an :class:`Identity`; the route mints a request id, calls
``OrchestrationService.handle_turn``, and returns the assembled response. The
service is resolved from ``app.state`` so tests can inject a fake.
"""
from __future__ import annotations

from bi_auth import Identity
from bi_base import new_request_id
from fastapi import APIRouter, Depends, HTTPException, Request

from enterprise_bi.api.models import AskRequest, AskResponse


def build_conversation_router(auth_dep) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["conversation"])

    @router.post("/ask", response_model=AskResponse)
    async def ask(
        body: AskRequest,
        request: Request,
        identity: Identity = Depends(auth_dep),
    ) -> AskResponse:
        service = getattr(request.app.state, "orchestration_service", None)
        if service is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "SERVICE_UNAVAILABLE", "message": "orchestration service not configured"},
            )
        result = service.handle_turn(
            question=body.question,
            identity=identity,
            request_id=new_request_id(),
            history=[h.model_dump() for h in body.history],
        )
        return AskResponse(**result)

    return router
