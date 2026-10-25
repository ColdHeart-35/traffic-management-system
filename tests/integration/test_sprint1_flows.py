"""Sprint 1 end-to-end flows across modules (Likhita, QA): sensor -> controller -> audit, RBAC, config."""
from __future__ import annotations

from tms.common import clock
from tms.detection.synthetic import generate_events

BASE = "/api/v1/intersections/INT-001"


def post_events(client, sensor_h, events):
    for event in events:
        assert client.post("/api/v1/detections", json=event, headers=sensor_h).status_code == 201


def test_traffic_flows_from_sensor_to_a_longer_green_and_into_the_audit_log(client, sensor_h, operator_h, admin_h):
    before = client.get(f"{BASE}/signal-state", headers=operator_h).json()["plan"]["green"]
    post_events(client, sensor_h, generate_events("INT-001", seed=4, minutes=5,
                                                  vehicles_per_minute={"N": 20, "S": 20, "E": 3, "W": 3}))
    clock.advance(95)
    state = client.post(f"{BASE}/signal-control/tick", headers=operator_h)
    assert state.status_code == 200
    after = client.get(f"{BASE}/signal-state", headers=operator_h).json()["plan"]["green"]
    assert after["NS"] > before["NS"] and after["EW"] < before["EW"]
    log = client.get(f"{BASE}/audit-log", headers=admin_h, params={"event": "plan_applied"}).json()
    assert log and log[0]["source"] == "auto"


def test_a_pedestrian_is_served_and_the_request_clears(client, sensor_h, operator_h):
    client.get(f"{BASE}/signal-state", headers=operator_h)
    ped = {"intersectionId": "INT-001", "timestamp": "2026-10-19T09:00:05Z", "sourceId": "xwalk",
           "detectionType": "pedestrian", "count": 1, "confidence": 0.9}
    post_events(client, sensor_h, [ped])
    assert len(client.get(f"{BASE}/pedestrian-requests", headers=operator_h).json()) == 1
    clock.advance(50)
    client.post(f"{BASE}/signal-control/tick", headers=operator_h)
    assert client.get(f"{BASE}/signal-state", headers=operator_h).json()["phase"] == "PED"
    assert client.get(f"{BASE}/pedestrian-requests", headers=operator_h).json() == []


def test_a_configuration_change_by_the_administrator_reaches_the_controller(client, admin_h, operator_h):
    assert client.put("/api/v1/admin/intersections/INT-001/config",
                      json={"changes": {"min_green": 12, "max_green": 50}}, headers=admin_h).status_code == 200
    clock.advance(95)
    client.post(f"{BASE}/adaptive/recompute", headers=operator_h)
    plan = client.get(f"{BASE}/signal-state", headers=operator_h).json()["plan"]["green"]
    assert all(12 <= v <= 50 for v in plan.values())


def test_each_role_sees_only_its_own_modules(client, operator_h, analyst_h, admin_h):
    assert client.get("/api/v1/simulation/samples", headers=operator_h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=operator_h).status_code == 403
    assert client.get(f"{BASE}/audit-log", headers=analyst_h).status_code == 403
    assert client.get("/api/v1/simulation/samples", headers=analyst_h).status_code == 200
    assert client.get("/api/v1/admin/users", headers=admin_h).status_code == 200
    denied = client.get("/api/v1/admin/security-log", headers=admin_h).json()
    assert len([r for r in denied if r["event"] == "access_denied"]) >= 3


def test_every_page_renders(client):
    for path in ("/", "/operator", "/detection", "/simulation", "/incidents", "/reports", "/admin"):
        assert client.get(path).status_code == 200, path
