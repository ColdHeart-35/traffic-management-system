"""Scenario comparison (TMS-F-012) and replay (TMS-F-013), tests TC-Sim-04 and TC-Sim-05."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tms.common.errors import ValidationFailure
from tms.simulation import compare as compare_mod

BASE = "/api/v1/simulation"
SAMPLE = json.loads((Path(__file__).resolve().parents[3] / "data" / "sample_networks" / "single_intersection.json").read_text())

FIXED = {"name": "Fixed timing"}
STARVED = {"name": "Short NS green", "greenOverrides": {"X": {"NS": 5}}}


def network_id(client, headers):
    return client.post(f"{BASE}/networks/import-sample", json={"name": "single_intersection"}, headers=headers).json()["id"]


def compare(client, headers, scenarios, **extra):
    body = {"networkId": network_id(client, headers), "durationSeconds": 1800, "demandScale": 2.0,
            "scenarios": scenarios, **extra}
    return client.post(f"{BASE}/comparisons", json=body, headers=headers)


# ---------- comparison ----------

def test_TC_Sim_04_two_scenarios_are_compared_against_the_baseline(client, analyst_h):
    response = compare(client, analyst_h, [FIXED, STARVED])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["baseline"] == "Fixed timing"
    assert [s["name"] for s in body["scenarios"]] == ["Fixed timing", "Short NS green"]
    assert all(s["metrics"]["vehiclesEntered"] > 0 for s in body["scenarios"])
    diff = body["differences"][0]
    assert diff["name"] == "Short NS green" and diff["against"] == "Fixed timing"
    assert diff["averageDelaySeconds"]["absolute"] > 0          # starving the busy approach adds delay
    assert body["best"]["averageDelaySeconds"] == "Fixed timing"
    assert "do not replace" in body["disclaimer"]


def test_a_scenario_compared_with_itself_has_no_difference(client, analyst_h):
    body = compare(client, analyst_h, [{"name": "A"}, {"name": "B"}]).json()
    for key in ("averageDelaySeconds", "averageQueueLength", "maxQueueLength", "throughputPerHour"):
        assert body["differences"][0][key]["absolute"] == 0
    assert set(body["best"].values()) == {"tie"}


def test_scenarios_share_the_seed_so_the_same_settings_give_the_same_result(client, analyst_h):
    first = compare(client, analyst_h, [FIXED, STARVED]).json()
    second = compare(client, analyst_h, [FIXED, STARVED]).json()
    assert first["scenarios"][1]["metrics"]["averageDelaySeconds"] == second["scenarios"][1]["metrics"]["averageDelaySeconds"]


def test_demand_can_differ_per_scenario(client, analyst_h):
    body = compare(client, analyst_h, [{"name": "Normal", "demandScale": 1.0}, {"name": "Busy", "demandScale": 3.0}]).json()
    assert body["scenarios"][1]["metrics"]["vehiclesEntered"] > body["scenarios"][0]["metrics"]["vehiclesEntered"]


@pytest.mark.parametrize("scenarios", [
    [FIXED],                                                     # too few
    [{"name": f"s{i}"} for i in range(6)],                       # too many
    [{"name": "same"}, {"name": "Same"}],                        # duplicate names, any case
    [{"name": "a"}, {"name": "   "}],                            # blank name
])
def test_bad_scenario_lists_are_rejected(client, analyst_h, scenarios):
    response = compare(client, analyst_h, scenarios)
    assert response.status_code == 422, response.text


def test_five_scenarios_are_allowed(client, analyst_h):
    assert compare(client, analyst_h, [{"name": f"s{i}"} for i in range(5)]).status_code == 201


def test_bad_green_override_is_rejected(client, analyst_h):
    response = compare(client, analyst_h, [FIXED, {"name": "zero", "greenOverrides": {"X": {"NS": 0}}}])
    assert response.status_code == 422


def test_unknown_network_is_404(client, analyst_h):
    response = client.post(f"{BASE}/comparisons", json={"networkId": 999, "scenarios": [FIXED, STARVED]}, headers=analyst_h)
    assert response.status_code == 404 and response.json()["error"] == "network_not_found"


def test_comparison_can_be_listed_and_read_back(client, analyst_h):
    created = compare(client, analyst_h, [FIXED, STARVED]).json()
    listing = client.get(f"{BASE}/comparisons", headers=analyst_h).json()
    assert listing[0]["comparisonId"] == created["comparisonId"] and listing[0]["scenarios"] == ["Fixed timing", "Short NS green"]
    again = client.get(f"{BASE}/comparisons/{created['comparisonId']}", headers=analyst_h).json()
    assert again["differences"] == created["differences"] and again["best"] == created["best"]
    missing = client.get(f"{BASE}/comparisons/999", headers=analyst_h)
    assert missing.status_code == 404 and missing.json()["error"] == "comparison_not_found"


def test_every_scenario_is_also_stored_as_a_run(client, analyst_h):
    created = compare(client, analyst_h, [FIXED, STARVED]).json()
    run_ids = [s["runId"] for s in created["scenarios"]]
    for run_id in run_ids:
        assert client.get(f"{BASE}/runs/{run_id}", headers=analyst_h).status_code == 200


def test_comparison_roles(client, operator_h, analyst_h, admin_h):
    assert client.get(f"{BASE}/comparisons").status_code == 401
    assert client.get(f"{BASE}/comparisons", headers=operator_h).status_code == 403
    assert client.get(f"{BASE}/comparisons", headers=admin_h).status_code == 200
    body = {"networkId": 1, "scenarios": [FIXED, STARVED]}
    assert client.post(f"{BASE}/comparisons", json=body, headers=operator_h).status_code == 403


def test_best_picks_the_highest_throughput_and_the_lowest_delay():
    # unit test of the pure scoring rule using fake results
    assert compare_mod.COMPARED["throughputPerHour"] is True
    assert compare_mod.COMPARED["averageDelaySeconds"] is False


# ---------- replay ----------

def stored_run(client, headers, duration=600):
    nid = network_id(client, headers)
    run = client.post(f"{BASE}/runs", json={"networkId": nid, "durationSeconds": duration, "seed": 7}, headers=headers)
    assert run.status_code == 201
    return run.json()["runId"]


def test_TC_Sim_05_replay_matches_the_stored_run(client, analyst_h):
    run_id = stored_run(client, analyst_h)
    stored = client.get(f"{BASE}/runs/{run_id}/trajectories", headers=analyst_h).json()["trajectories"]
    replay = client.get(f"{BASE}/runs/{run_id}/replay", headers=analyst_h).json()
    assert replay["runId"] == run_id and replay["speed"] == 1.0
    assert replay["vehicleCount"] == len(stored)
    assert replay["frameCount"] == len(replay["frames"]) > 0
    times = [f["t"] for f in replay["frames"]]
    assert times == sorted(times) and len(set(times)) == len(times)
    points_stored = sum(len(v["points"]) for v in stored)
    assert sum(len(f["vehicles"]) for f in replay["frames"]) == points_stored   # nothing lost or invented


@pytest.mark.parametrize("speed,interval", [("0.5", 10.0), ("1", 5.0), ("2", 2.5), ("4", 1.25), ("8", 0.625)])
def test_each_speed_scales_the_playback_interval(client, analyst_h, speed, interval):
    run_id = stored_run(client, analyst_h)
    replay = client.get(f"{BASE}/runs/{run_id}/replay", params={"speed": speed}, headers=analyst_h).json()
    assert replay["playbackIntervalSeconds"] == interval and replay["speed"] == float(speed)


@pytest.mark.parametrize("speed", ["0", "3", "16", "-1", "fast", ""])
def test_invalid_speeds_are_rejected(client, analyst_h, speed):
    run_id = stored_run(client, analyst_h)
    response = client.get(f"{BASE}/runs/{run_id}/replay", params={"speed": speed}, headers=analyst_h)
    assert response.status_code == 422 and response.json()["error"] == "invalid_speed"


def test_replay_of_an_unknown_run_is_404(client, analyst_h):
    response = client.get(f"{BASE}/runs/999/replay", headers=analyst_h)
    assert response.status_code == 404 and response.json()["error"] == "run_not_found"


def test_replay_roles(client, operator_h, analyst_h):
    run_id = stored_run(client, analyst_h)
    assert client.get(f"{BASE}/runs/{run_id}/replay").status_code == 401
    assert client.get(f"{BASE}/runs/{run_id}/replay", headers=operator_h).status_code == 403


def test_replay_frames_helper_handles_no_vehicles():
    empty = compare_mod.replay_frames([], 2.0)
    assert empty["frameCount"] == 0 and empty["frames"] == [] and empty["playbackIntervalSeconds"] == 2.5


def test_parse_speed_accepts_numbers_and_rejects_junk():
    assert compare_mod.parse_speed(8) == 8.0 and compare_mod.parse_speed("0.5") == 0.5
    with pytest.raises(ValidationFailure):
        compare_mod.parse_speed(None)
