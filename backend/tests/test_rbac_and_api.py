"""RBAC enforcement through the graph, and the HTTP boundary end-to-end."""
from __future__ import annotations

from bi_auth import JwtValidator, Role, mint_dev_token

from enterprise_bi.app.factory import create_app
from enterprise_bi.config.settings import Settings

SECRET = "test-secret"


def test_sales_role_blocked_from_revenue(service, sales_user):
    # SALES is not granted REVENUE; the offline planner emits a REVENUE query for
    # a revenue question, so the validate node must block it at the RBAC gate.
    resp = service.handle_turn(
        question="show revenue by branch", identity=sales_user, request_id="rid-rbac"
    )
    assert resp["status"] == "BLOCKED"
    assert resp["error"]["code"] == "SQL_UNSAFE"


def test_analyst_allowed_collections(service, analyst):
    resp = service.handle_turn(
        question="show collections by branch", identity=analyst, request_id="rid-ok"
    )
    assert resp["status"] == "OK"


def _client(service):
    from fastapi.testclient import TestClient

    settings = Settings(jwt_secret=SECRET, jwt_audience="enterprise-bi", jwt_issuers=["enterprise-bi-dev"])
    validator = JwtValidator(secret=SECRET, audience="enterprise-bi", issuers=["enterprise-bi-dev"])
    app = create_app(settings, service=service, validator=validator)
    return TestClient(app)


def test_health_open(service):
    client = _client(service)
    assert client.get("/health").json()["status"] == "ok"


def test_ask_requires_auth(service):
    client = _client(service)
    r = client.post("/api/v1/ask", json={"question": "show collections"})
    assert r.status_code == 401


def test_ask_end_to_end_with_token(service):
    client = _client(service)
    token = mint_dev_token(
        secret=SECRET, user_id="1", username="analyst", role=Role.BUSINESS_ANALYST,
        audience="enterprise-bi", issuer="enterprise-bi-dev",
    )
    r = client.post(
        "/api/v1/ask",
        json={"question": "show total collections by branch"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK"
    assert body["row_count"] == 3
    assert body["insight"]["summary"]
