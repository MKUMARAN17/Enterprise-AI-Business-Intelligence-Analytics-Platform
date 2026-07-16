"""Dev-only token minting.

Prod tokens are issued by the corporate IdP; this helper exists so local dev,
tests, and the `scripts/mint_dev_token.py` CLI can produce HS256 tokens that the
same :class:`JwtValidator` accepts. Never used in the prod signing path.
"""
from __future__ import annotations

import datetime as _dt

import jwt

from bi_auth.models import Role


def mint_dev_token(
    *,
    secret: str,
    user_id: str,
    username: str,
    role: Role | str,
    audience: str = "enterprise-bi",
    issuer: str = "enterprise-bi-dev",
    ttl_seconds: int = 3600,
    tenant: str | None = None,
) -> str:
    role_value = role.value if isinstance(role, Role) else Role.parse(role).value
    now = _dt.datetime.now(tz=_dt.UTC)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role_value,
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + _dt.timedelta(seconds=ttl_seconds),
    }
    if tenant:
        payload["tid"] = tenant
    return jwt.encode(payload, secret, algorithm="HS256")
