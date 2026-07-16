"""DEV-ONLY sign-in route.

Mirrors the reference frontend's ``authMode="dev"``: the backend mints a
short-lived HS256 token for a chosen role so the SPA can authenticate locally
without a corporate IdP. Mounted ONLY when ``BI_ALLOW_DEV_LOGIN=true`` and an
HS256 ``jwt_secret`` is configured — it is an authentication bypass and must
never be enabled in production.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bi_auth import Role, mint_dev_token


class DevLoginRequest(BaseModel):
    role: str = Field(default="BUSINESS_ANALYST")
    username: str | None = None


class DevLoginResponse(BaseModel):
    token: str
    role: str
    username: str


def build_dev_router(*, secret: str, audience: str, issuer: str, ttl_seconds: int = 3600) -> APIRouter:
    router = APIRouter(prefix="/api/v1/dev", tags=["dev"])

    @router.post("/login", response_model=DevLoginResponse)
    async def dev_login(body: DevLoginRequest) -> DevLoginResponse:
        try:
            role = Role.parse(body.role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "BAD_ROLE", "message": str(exc)}) from exc
        username = body.username or role.value.lower()
        token = mint_dev_token(
            secret=secret,
            user_id=username,
            username=username,
            role=role,
            audience=audience,
            issuer=issuer,
            ttl_seconds=ttl_seconds,
        )
        return DevLoginResponse(token=token, role=role.value, username=username)

    return router
