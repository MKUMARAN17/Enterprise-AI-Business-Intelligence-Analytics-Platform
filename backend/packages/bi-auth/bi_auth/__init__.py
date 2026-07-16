"""bi-auth — JWT authentication + RBAC for the Enterprise BI platform.

    from bi_auth import JwtValidator, Identity, Role, RbacPolicy

    validator = JwtValidator(secret="...", audience="enterprise-bi")
    identity = validator.validate(bearer_token)         # -> Identity (or AuthError)
    allowed = RbacPolicy().allowed_tables(identity.role)  # -> set of UPPERCASE tables

Fail-closed: every validation problem raises ``bi_base.AuthError``; there is no
anonymous path. The RBAC allow-list is handed to the SQL guard so a query can
only touch tables the caller's role is granted.
"""
from __future__ import annotations

from bi_auth.jwt_validator import JwtValidator
from bi_auth.models import Identity, Role
from bi_auth.rbac import RbacPolicy
from bi_auth.tokens import mint_dev_token

__version__ = "0.1.0"

__all__ = [
    "JwtValidator",
    "Identity",
    "Role",
    "RbacPolicy",
    "mint_dev_token",
    "__version__",
]
