"""Auth value types: the roles and the authenticated Identity.

``Role`` mirrors the ROLES table's ROLE_NAME values exactly (UPPERCASE) so the
JWT's ``role`` claim, the seed data, and the RBAC policy all agree. ``Identity``
is the immutable, validated fact the rest of the app trusts — it is minted only
by the JWT validator, never constructed from unvalidated request input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    BUSINESS_ANALYST = "BUSINESS_ANALYST"
    MANAGER = "MANAGER"
    FINANCE = "FINANCE"
    SALES = "SALES"
    ADMIN = "ADMIN"

    @classmethod
    def parse(cls, value: str) -> Role:
        try:
            return cls(value.strip().upper())
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"unknown role: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class Identity:
    """An authenticated business user (minted from a verified JWT)."""

    user_id: str
    username: str
    role: Role
    tenant: str | None = None
    claims: dict = field(default_factory=dict)
