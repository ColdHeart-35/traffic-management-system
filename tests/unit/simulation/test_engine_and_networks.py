"""Network validation, the simulation engine and its metrics (Naveen): TMS-F-009, TMS-F-010, TMS-F-011."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

from tms.common.errors import ValidationFailure
from tms.simulation.engine import run_simulation
from tms.simulation.metrics import compute_metrics
from tms.simulation.network import NetworkValidationError, validate_network

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "sample_networks"


def load(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text())


@pytest.fixture
def single() -> dict:
    return load("single_intersection")


def test_both_sample_networks_are_valid():
    assert validate_network(load("single_intersection")) == []
    assert validate_network(load("corridor_3")) == []


def test_TC_Sim_01_orphan_nodes_and_links_are_reported(single):
    single["nodes"].append({"id": "LOST", "type": "junction"})
    single["links"].append({"id": "BAD", "from": "A", "to": "GHOST", "length_m": 50})
    errors = validate_network(single)
    assert any("orphan node LOST" in e for e in errors)
    assert any("orphan link BAD" in e and "GHOST" in e for e in errors)


def test_unreachable_exit_is_reported(single):
    single["demand"] = [{"link": "A_X", "rate_per_hour": 100}]
    single["nodes"][2]["turns"] = {"A_X": {"X_C": 1.0}, "B_X": {"X_C": 1.0}}
    single["links"] = [l for l in single["links"] if l["id"] != "X_D"]
    single["nodes"] = [n for n in single["nodes"] if n["id"] != "D"]
    assert validate_network(single) == []                 # one exit left, still reachable
    single["nodes"].append({"id": "D", "type": "exit"})
    assert validate_network(single)                       # an exit nobody can reach


@pytest.mark.parametrize("broken", [None, [], {}, {"nodes": []}, {"nodes": [{"id": "A", "type": "entry"}]}])
def test_garbage_is_rejected_not_crashed(broken):
    assert validate_network(broken)


def test_bad_values_are_reported(single):
    single["links"][0]["length_m"] = -5
    single["nodes"][0]["type"] = "spaceport"
    single["demand"][1]["rate_per_hour"] = -1
    errors = " | ".join(validate_network(single))
    assert "length_m" in errors and "spaceport" in errors and "rate_per_hour" in errors


def test_duplicate_ids_are_reported(single):
    single["nodes"].append({"id": "A", "type": "entry"})
    single["links"].append(dict(single["links"][0]))
    errors = " | ".join(validate_network(single))
    assert "duplicate node id A" in errors and "duplicate link id A_X" in errors


def test_running_an_invalid_network_raises(single):
    single["links"][0]["to"] = "GHOST"
    with pytest.raises(NetworkValidationError):
        run_simulation(single, {"duration_seconds": 60})


def test_TC_Sim_02_same_seed_gives_the_same_result_and_a_new_seed_differs(single):
    params = {"duration_seconds": 600, "seed": 11}
    first, second = run_simulation(single, params), run_simulation(single, params)
    assert first == second
    assert run_simulation(single, {**params, "seed": 12}) != first


def test_vehicles_are_conserved(single):
    result = run_simulation(single, {"duration_seconds": 900})
    assert result["vehiclesEntered"] == result["vehiclesCompleted"] + result["vehiclesInNetwork"]
    assert result["vehiclesEntered"] > 0


def test_no_demand_means_no_vehicles(single):
    result = run_simulation(single, {"duration_seconds": 300, "demand_scale": 0})
    metrics = compute_metrics(result)
    assert (metrics["vehiclesEntered"], metrics["throughputPerHour"], metrics["averageDelaySeconds"]) == (0, 0.0, 0.0)


def test_more_demand_means_more_vehicles(single):
    light = run_simulation(single, {"duration_seconds": 1200, "demand_scale": 0.5})
    heavy = run_simulation(single, {"duration_seconds": 1200, "demand_scale": 2.0})
    assert heavy["vehiclesEntered"] > light["vehiclesEntered"]


def test_TC_Sim_03_metrics_are_complete_and_quick(single):
    result = run_simulation(single, {"duration_seconds": 3600})
    started = time.perf_counter()
    metrics = compute_metrics(result)
    assert time.perf_counter() - started < 5
    for key in ("averageDelaySeconds", "averageQueueLength", "maxQueueLength", "throughputPerHour", "disclaimer"):
        assert key in metrics
    assert metrics["averageDelaySeconds"] >= 0 and metrics["throughputPerHour"] > 0
    assert "do not replace" in metrics["disclaimer"]


def test_changing_the_green_time_changes_the_delay(single):
    base = compute_metrics(run_simulation(single, {"duration_seconds": 3600, "demand_scale": 2}))
    starved = compute_metrics(run_simulation(single, {"duration_seconds": 3600, "demand_scale": 2,
                                                       "green_overrides": {"X": {"NS": 5}}}))
    assert starved["averageDelaySeconds"] > base["averageDelaySeconds"]


@pytest.mark.parametrize("params", [
    {"duration_seconds": 5}, {"duration_seconds": 10**6}, {"duration_seconds": "x"}, {"demand_scale": 9},
    {"demand_scale": -1}, {"green_overrides": {"X": {"NS": 0}}},
])
def test_bad_parameters_are_rejected(single, params):
    with pytest.raises(ValidationFailure):
        run_simulation(single, {"duration_seconds": 300, **params})


def test_corridor_runs_and_every_signal_is_used():
    result = run_simulation(load("corridor_3"), {"duration_seconds": 900})
    assert result["vehiclesCompleted"] > 0
    assert result["queue"]["approachLinks"] >= 3
