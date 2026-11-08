"""Emergency-vehicle preemption (Manoj): TMS-F-004, test case TC-Sig-04."""
from __future__ import annotations

import pytest

from tms.common.errors import CommandError
from tms.detection import pedestrian
from tms.signal_control import audit, controller, preemption
from tms.signal_control.models import SignalState

from tests.conftest import after

IID = "INT-001"
KEY = {"X-Preemption-Key": "preempt-demo-key"}


def start(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()


def test_TC_Sig_04_preemption_is_applied_within_3_seconds_and_the_corridor_turns_green(session):
    start(session)
    result = preemption.request_preemption(session, IID, "E", "AMB-7", 30, now=after(5))   # NS is green, E is on EW
    assert result["phase"] == "EW"
    assert (result["appliedAt"]) == after(5).isoformat()
    state = session.get(SignalState, IID)
    assert (state.stage, state.phase) == ("YELLOW", "NS")          # clearance started within a second
    assert (state.stage_started_at - after(5)).total_seconds() <= 1
    assert result["greenWithinSeconds"] == 5                       # yellow 3 + all-red 2, never skipped

    state = controller.tick(session, IID, after(12))
    assert (state.phase, state.stage, state.mode) == ("EW", "GREEN", "manual")
    assert state.control_source == "preemption"


def test_a_corridor_that_is_already_green_stays_green_with_no_clearance(session):
    start(session)
    result = preemption.request_preemption(session, IID, "N", "AMB-7", 30, now=after(5))
    assert result["greenWithinSeconds"] == 0
    assert controller.tick(session, IID, after(30)).stage == "GREEN"


def test_normal_operation_resumes_after_the_hold_or_when_cleared(session):
    start(session)
    preemption.request_preemption(session, IID, "E", "AMB-7", 20, now=after(5))
    assert controller.tick(session, IID, after(60)).mode == "adaptive"          # hold ended by itself
    assert audit.count_events(session, IID, "preemption_cleared") == 1

    preemption.request_preemption(session, IID, "N", "AMB-8", 60, now=after(100))
    cleared = preemption.clear_preemption(session, IID, "AMB-8", now=after(110))
    assert cleared["mode"] == "adaptive"
    assert audit.count_events(session, IID, "preemption_cleared") == 2
    assert preemption.clear_preemption(session, IID, "AMB-8", now=after(111))["status"] == "no_active_preemption"


def test_every_preemption_state_change_is_audited_as_preemption(session):
    start(session)
    preemption.request_preemption(session, IID, "E", "AMB-7", 30, now=after(5))
    controller.tick(session, IID, after(12))
    sources = [row["source"] for row in audit.list_events(session, IID, event="phase_change", limit=4)]
    assert sources[:2] == ["preemption", "preemption"]
    entry = audit.list_events(session, IID, event="preemption_applied")[0]
    assert entry["details"]["vehicleId"] == "AMB-7" and entry["details"]["approach"] == "E"


def test_an_emergency_vehicle_may_cut_a_pedestrian_stage_short_but_an_operator_may_not(session):
    start(session)
    pedestrian.request_crossing(session, IID, after(10))
    session.commit()
    result = preemption.request_preemption(session, IID, "E", "AMB-7", 30, now=after(50))   # PED runs 45 to 67
    assert result["status"] == "applied"
    assert audit.list_events(session, IID, event="preemption_applied")[0]["details"]["pedestrianInterrupted"] is True


@pytest.mark.parametrize("approach,vehicle,hold,code", [
    ("Q", "A1", 30, "invalid_approach"), ("N", "", 30, "invalid_vehicle"),
    ("N", "A1", 5, "invalid_duration"), ("N", "A1", 999, "invalid_duration"),
])
def test_bad_requests_are_rejected(session, approach, vehicle, hold, code):
    start(session)
    with pytest.raises(CommandError) as caught:
        preemption.request_preemption(session, IID, approach, vehicle, hold, now=after(5))
    assert caught.value.code == code


def test_api_needs_the_secure_channel_key(client):
    body = {"approach": "E", "vehicleId": "AMB-7"}
    base = f"/api/v1/intersections/{IID}/preemption"
    assert client.post(base, json=body).status_code == 401
    assert client.post(base, json=body, headers={"X-Preemption-Key": "wrong"}).status_code == 403
    assert client.post(base, json=body, headers={"X-API-Key": "sensor-demo-key"}).status_code == 401  # not the sensor key
    ok = client.post(base, json=body, headers=KEY)
    assert ok.status_code == 201 and ok.json()["phase"] == "EW"
    assert client.post(f"{base}/clear", params={"vehicleId": "AMB-7"}, headers=KEY).json()["mode"] == "adaptive"
    assert client.post(base, json={"approach": "Z", "vehicleId": "A"}, headers=KEY).status_code == 400
    assert client.post("/api/v1/intersections/NOPE/preemption", json=body, headers=KEY).status_code == 404


def test_operators_still_see_the_preemption_in_the_state_and_audit_log(client, operator_h):
    client.post(f"/api/v1/intersections/{IID}/preemption", json={"approach": "E", "vehicleId": "AMB-7"}, headers=KEY)
    state = client.get(f"/api/v1/intersections/{IID}/signal-state", headers=operator_h).json()
    assert state["mode"] == "manual"
    log = client.get(f"/api/v1/intersections/{IID}/audit-log", params={"event": "preemption_applied"}, headers=operator_h)
    assert log.json()[0]["source"] == "preemption"
