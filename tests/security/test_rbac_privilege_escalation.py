"""Least-privilege role checks (Roshini): PRJ-SR-004, test case TC-Sec-05."""
from __future__ import annotations

import pytest

# (method, path, body) that only some roles may call
ADMIN_ONLY = [
    ("GET", "/api/v1/admin/users", None),
    ("POST", "/api/v1/admin/users", {"username": "evil", "password": "evil-pass-1", "role": "Administrator"}),
    ("PUT", "/api/v1/admin/users/analyst/role", {"role": "Administrator"}),
    ("PUT", "/api/v1/admin/intersections/INT-001/config", {"changes": {"min_green": 5}}),
    ("GET", "/api/v1/admin/security-log", None),
    ("POST", "/api/v1/admin/backups", None),
    ("GET", "/api/v1/security/alerts", None),
    ("POST", "/api/v1/admin/users/operator/mfa/reset", None),
]
OPERATOR_ONLY = [("POST", "/api/v1/intersections/INT-001/signal-command", {"mode": "auto"})]
ANALYST_AND_ADMIN = [("GET", "/api/v1/simulation/samples", None), ("GET", "/api/v1/reports", None)]


def call(client, method, path, body, headers):
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
def test_TC_Sec_05_low_privilege_roles_cannot_use_administrator_functions(client, operator_h, analyst_h, method, path, body):
    for headers in (operator_h, analyst_h, {}):
        assert call(client, method, path, body, headers).status_code in (401, 403), (path, headers)


def test_TC_Sec_05_every_denied_attempt_is_logged(client, operator_h, analyst_h, admin_h):
    attempts = [(operator_h, *ADMIN_ONLY[0]), (analyst_h, *ADMIN_ONLY[1]), (analyst_h, *ADMIN_ONLY[3])]
    for headers, method, path, body in attempts:
        assert call(client, method, path, body, headers).status_code == 403
    log = client.get("/api/v1/admin/security-log", headers=admin_h).json()
    denied = [row for row in log if row["event"] == "access_denied"]
    assert {row["user"] for row in denied} == {"operator", "analyst"} and len(denied) == 3


def test_a_user_cannot_promote_themselves(client, analyst_h, admin_h):
    assert client.put("/api/v1/admin/users/analyst/role", json={"role": "Administrator"}, headers=analyst_h).status_code == 403
    users = {u["username"]: u["role"] for u in client.get("/api/v1/admin/users", headers=admin_h).json()}
    assert users["analyst"] == "Analyst"


@pytest.mark.parametrize("method,path,body", OPERATOR_ONLY)
def test_signal_commands_are_for_operators_only(client, analyst_h, admin_h, method, path, body):
    assert call(client, method, path, body, analyst_h).status_code == 403
    assert call(client, method, path, body, admin_h).status_code == 403


@pytest.mark.parametrize("method,path,body", ANALYST_AND_ADMIN)
def test_analyst_functions_are_closed_to_operators(client, operator_h, analyst_h, method, path, body):
    assert call(client, method, path, body, operator_h).status_code == 403
    assert call(client, method, path, body, analyst_h).status_code == 200


def test_a_token_does_not_carry_over_a_role_change_it_is_checked_each_time(client, analyst_h, admin_h):
    assert client.get("/api/v1/simulation/samples", headers=analyst_h).status_code == 200
    client.put("/api/v1/admin/users/analyst/role", json={"role": "Operator"}, headers=admin_h)
    assert client.get("/api/v1/simulation/samples", headers=analyst_h).status_code == 403


def test_least_privilege_defaults_for_a_new_user_role_must_be_chosen_explicitly(client, admin_h):
    assert client.post("/api/v1/admin/users", json={"username": "x", "password": "long-enough-1"}, headers=admin_h).status_code == 422
    assert client.post("/api/v1/admin/users", json={"username": "x", "password": "long-enough-1", "role": "Root"}, headers=admin_h).status_code == 400
