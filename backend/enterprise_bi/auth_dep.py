"""FastAPI auth dependency factory (thin adapter over bi_auth.JwtValidator).

Kept out of bi-auth so that package stays framework-free. Given a validator, it
returns a dependency that extracts the bearer token, validates it, and yields the
:class:`Identity` — raising 401 on any failure (fail-closed).
"""
from __future__ import annotations

from bi_auth import Identity, JwtValidator
from bi_base import AuthError, bind_request
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def make_auth_dependency(validator: JwtValidator):
    async def dependency(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Identity:
        if creds is None or not creds.credentials:
            raise HTTPException(status_code=401, detail={"code": "AUTH_ERROR", "message": "missing bearer token"})
        try:
            identity = validator.validate(creds.credentials)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=exc.to_problem()) from exc
        bind_request(user_id=identity.user_id)
        return identity

    return dependency
