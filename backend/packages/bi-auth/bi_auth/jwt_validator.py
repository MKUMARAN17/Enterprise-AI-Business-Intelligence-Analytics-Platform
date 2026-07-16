"""Fail-closed JWT validation.

The sole authentication mechanism (functional requirement: "Users authenticate
using JWT"). A single :class:`JwtValidator` is built once at boot and validates
every bearer token, returning a typed :class:`Identity`. It fails *closed*: any
problem — bad signature, expired, wrong audience/issuer, missing role claim,
unknown role — raises :class:`bi_base.AuthError`; there is no anonymous path and
no "verification skipped" branch.

Two algorithm families are supported so dev and prod share one code path:
  * HS256 with a shared secret (local dev / tests — `mint_dev_token`),
  * RS256 with a PEM public key (prod — the IdP signs, we verify).
"""
from __future__ import annotations

import jwt
from bi_base.errors import AuthError, ConfigError

from bi_auth.models import Identity, Role


class JwtValidator:
    def __init__(
        self,
        *,
        secret: str | None = None,
        public_key: str | None = None,
        algorithms: list[str] | None = None,
        audience: str | None = None,
        issuers: list[str] | None = None,
        leeway_seconds: int = 30,
    ):
        if not secret and not public_key:
            raise ConfigError("JwtValidator needs either a shared secret or a public key")
        self._key = public_key or secret
        self._algorithms = algorithms or (["RS256"] if public_key else ["HS256"])
        self._audience = audience
        self._issuers = issuers or []
        self._leeway = leeway_seconds

    def validate(self, token: str) -> Identity:
        """Verify ``token`` and return the caller's Identity, or raise AuthError."""
        if not token:
            raise AuthError("missing bearer token")
        options = {"require": ["exp"]}
        try:
            payload = jwt.decode(
                token,
                self._key,
                algorithms=self._algorithms,
                audience=self._audience if self._audience else None,
                options={**options, "verify_aud": bool(self._audience)},
                leeway=self._leeway,
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthError("invalid audience") from exc
        except jwt.PyJWTError as exc:
            raise AuthError(f"invalid token: {exc}") from exc

        if self._issuers:
            iss = payload.get("iss")
            if iss not in self._issuers:
                raise AuthError("untrusted issuer")

        role_claim = payload.get("role")
        if not role_claim:
            raise AuthError("token missing 'role' claim")
        try:
            role = Role.parse(str(role_claim))
        except ValueError as exc:
            raise AuthError(str(exc)) from exc

        sub = payload.get("sub")
        if not sub:
            raise AuthError("token missing 'sub' claim")

        return Identity(
            user_id=str(sub),
            username=str(payload.get("username", sub)),
            role=role,
            tenant=payload.get("tid"),
            claims=payload,
        )
