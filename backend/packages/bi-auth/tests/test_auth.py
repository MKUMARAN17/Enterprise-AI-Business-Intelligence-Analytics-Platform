from __future__ import annotations

import pytest
from bi_base.errors import AuthError

from bi_auth import Identity, JwtValidator, RbacPolicy, Role, mint_dev_token

SECRET = "test-secret"
AUD = "enterprise-bi"
ISS = "enterprise-bi-dev"


def _token(**kw):
    kw.setdefault("secret", SECRET)
    kw.setdefault("user_id", "1")
    kw.setdefault("username", "analyst")
    kw.setdefault("role", Role.BUSINESS_ANALYST)
    return mint_dev_token(**kw)


def _validator(**kw):
    kw.setdefault("secret", SECRET)
    kw.setdefault("audience", AUD)
    kw.setdefault("issuers", [ISS])
    return JwtValidator(**kw)


def test_valid_token_yields_identity():
    ident = _validator().validate(_token())
    assert isinstance(ident, Identity)
    assert ident.role is Role.BUSINESS_ANALYST
    assert ident.username == "analyst"


def test_expired_token_rejected():
    tok = _token(ttl_seconds=-3600)  # well beyond the validator's 30s leeway
    with pytest.raises(AuthError):
        _validator().validate(tok)


def test_wrong_audience_rejected():
    tok = _token(audience="other-app")
    with pytest.raises(AuthError):
        _validator().validate(tok)


def test_untrusted_issuer_rejected():
    tok = _token(issuer="evil")
    with pytest.raises(AuthError):
        _validator().validate(tok)


def test_bad_signature_rejected():
    tok = _token()
    v = _validator(secret="different-secret")
    with pytest.raises(AuthError):
        v.validate(tok)


def test_missing_token_rejected():
    with pytest.raises(AuthError):
        _validator().validate("")


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        Role.parse("SUPERUSER")


def test_rbac_admin_sees_everything():
    pol = RbacPolicy()
    assert "AUDIT_LOG" in pol.allowed_tables(Role.ADMIN)
    assert pol.can_read(Role.ADMIN, "REVENUE")


def test_rbac_sales_cannot_read_finance_tables():
    pol = RbacPolicy()
    assert not pol.can_read(Role.SALES, "CLAIMS")
    assert not pol.can_read(Role.SALES, "PAYMENTS")
    assert pol.can_read(Role.SALES, "SALES")


def test_rbac_finance_cannot_read_sales_or_inventory():
    pol = RbacPolicy()
    assert not pol.can_read(Role.FINANCE, "INVENTORY")
    assert pol.can_read(Role.FINANCE, "REVENUE")


def test_rbac_analyst_no_platform_tables():
    pol = RbacPolicy()
    assert not pol.can_read(Role.BUSINESS_ANALYST, "USERS")
    assert pol.can_read(Role.BUSINESS_ANALYST, "COLLECTIONS")
