"""Sign-in, roles and the security log (Roshini): TMS-F-018, PRJ-SR-004."""
from __future__ import annotations

from sqlalchemy import select

from tms.admin import rbac
from tms.admin.models import SecurityLog, User


def _events(session) -> list[str]:
    return [row.event for row in session.scalars(select(SecurityLog).order_by(SecurityLog.id))]


def test_login_returns_token_and_role(client):
    response = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Analyst" and body["token"] and body["mfa"] is False


def test_wrong_password_is_rejected_and_logged(client, session):
    response = client.post("/api/v1/auth/login", json={"username": "operator", "password": "nope-nope"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"
    assert "login_failed" in _events(session)


def test_unknown_user_gets_the_same_answer_as_a_wrong_password(client):
    response = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_passwords_are_stored_hashed(session):
    user = session.scalar(select(User).where(User.username == "operator"))
    assert "operator123" not in user.password_hash
    assert rbac.verify_password("operator123", user.password_hash)
    assert not rbac.verify_password("wrong", user.password_hash)


def test_missing_or_bad_token_is_401_and_logged(client, session):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer made-up"}).status_code == 401
    assert _events(session).count("auth_failed") == 2


def test_me_lists_the_permissions_of_the_role(client, analyst_h):
    body = client.get("/api/v1/auth/me", headers=analyst_h).json()
    assert body["role"] == "Analyst"
    assert "run simulations" in body["permissions"]
    assert "override signals" not in body["permissions"]


def test_TC_Adm_01_analyst_is_denied_an_admin_function_and_it_is_logged(client, analyst_h, admin_h):
    denied = client.get("/api/v1/admin/users", headers=analyst_h)
    assert denied.status_code == 403
    log = client.get("/api/v1/admin/security-log", headers=admin_h).json()
    assert any(row["event"] == "access_denied" and row["user"] == "analyst" for row in log)


def test_least_privilege_defaults_for_admin_endpoints(client, operator_h, analyst_h):
    for headers in (operator_h, analyst_h):
        assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/security-log", headers=headers).status_code == 403
        assert client.put("/api/v1/admin/intersections/INT-001/config", json={"changes": {}},
                          headers=headers).status_code == 403


def test_administrator_creates_a_user_who_can_sign_in(client, admin_h):
    created = client.post("/api/v1/admin/users", headers=admin_h,
                          json={"username": "newop", "password": "longenough1", "role": "Operator"})
    assert created.status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "newop", "password": "longenough1"}).status_code == 200


def test_user_creation_rejects_bad_input(client, admin_h):
    def create(**fields):
        return client.post("/api/v1/admin/users", headers=admin_h, json=fields)

    assert create(username="x1", password="short", role="Operator").json()["error"] == "weak_password"
    assert create(username="x2", password="longenough1", role="Pilot").json()["error"] == "invalid_role"
    duplicate = create(username="operator", password="longenough1", role="Operator")
    assert duplicate.status_code == 409 and duplicate.json()["error"] == "user_exists"


def test_administrator_can_change_a_role(client, admin_h, analyst_h):
    changed = client.put("/api/v1/admin/users/analyst/role", headers=admin_h, json={"role": "Operator"})
    assert changed.status_code == 200 and changed.json()["role"] == "Operator"
    # the role is read on every request, so the existing token now has operator rights
    assert client.get("/api/v1/admin/users", headers=analyst_h).status_code == 403
    assert client.put("/api/v1/admin/users/ghost/role", headers=admin_h, json={"role": "Operator"}).status_code == 404


def test_roles_endpoint_lists_every_role(client, admin_h):
    assert set(client.get("/api/v1/admin/roles", headers=admin_h).json()) == set(rbac.ALL_ROLES)
