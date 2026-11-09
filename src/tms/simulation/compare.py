"""Scenario comparison (TMS-F-012) and replay frames (TMS-F-013).

A comparison runs several scenarios on the same network with the same seed, so any difference in
the results comes from the scenario (signal timing or demand) and not from random chance. The first
scenario is the baseline; every other scenario is compared against it.
"""
from __future__ import annotations

from tms.common.errors import ValidationFailure
from tms.simulation import metrics as metrics_mod
from tms.simulation.engine import run_simulation

MIN_SCENARIOS, MAX_SCENARIOS = 2, 5
REPLAY_SPEEDS = (0.5, 1.0, 2.0, 4.0, 8.0)
TRAJECTORY_STEP_SECONDS = 5          # how far apart the stored trajectory points are

# metric -> True when a higher value is better
COMPARED = {
    "averageDelaySeconds": False,
    "averageQueueLength": False,
    "maxQueueLength": False,
    "throughputPerHour": True,
}


def check_scenarios(scenarios: list[dict]) -> None:
    if not MIN_SCENARIOS <= len(scenarios) <= MAX_SCENARIOS:
        raise ValidationFailure(f"a comparison needs {MIN_SCENARIOS} to {MAX_SCENARIOS} scenarios, got {len(scenarios)}",
                                code="invalid_scenarios")
    names = [s["name"].strip() for s in scenarios]
    if any(not n for n in names):
        raise ValidationFailure("every scenario needs a name", code="invalid_scenarios")
    if len({n.lower() for n in names}) != len(names):
        raise ValidationFailure("scenario names must be unique", code="invalid_scenarios")


def _difference(base: float, value: float) -> dict:
    absolute = round(value - base, 2)
    percent = round(absolute / base * 100.0, 1) if base else None
    return {"absolute": absolute, "percent": percent}


def compare(network: dict, scenarios: list[dict], common: dict) -> dict:
    """Run every scenario and return per-scenario results, differences against the baseline and winners.

    ``common`` holds duration_seconds, seed and demand_scale shared by all scenarios; a scenario may
    override demand_scale and may set green_overrides. Each result keeps its raw run so the caller can store it.
    """
    check_scenarios(scenarios)
    results = []
    for scenario in scenarios:
        params = {**common, "green_overrides": scenario.get("green_overrides") or {}}
        if scenario.get("demand_scale") is not None:
            params["demand_scale"] = scenario["demand_scale"]
        raw = run_simulation(network, params)
        results.append({"name": scenario["name"].strip(), "params": raw["params"],
                        "metrics": metrics_mod.compute_metrics(raw), "trajectories": raw["trajectories"]})

    base = results[0]["metrics"]
    differences = []
    for item in results[1:]:
        differences.append({"name": item["name"], "against": results[0]["name"],
                            **{key: _difference(base[key], item["metrics"][key]) for key in COMPARED}})

    best = {}
    for key, higher_is_better in COMPARED.items():
        pick = max if higher_is_better else min
        values = [r["metrics"][key] for r in results]
        winners = [r["name"] for r in results if r["metrics"][key] == pick(values)]
        best[key] = winners[0] if len(winners) == 1 else "tie"
    return {"baseline": results[0]["name"], "scenarios": results, "differences": differences, "best": best,
            "disclaimer": metrics_mod.DISCLAIMER}


def parse_speed(value) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        speed = None
    if speed not in REPLAY_SPEEDS:
        raise ValidationFailure("speed must be one of 0.5, 1, 2, 4 or 8", code="invalid_speed")
    return speed


def replay_frames(trajectories: list[dict], speed: float) -> dict:
    """Group the stored trajectory points by simulated time so a viewer can play them back.

    ``playbackIntervalSeconds`` is the real time to wait between two frames at this speed.
    """
    frames: dict[int, list[dict]] = {}
    for vehicle in trajectories:
        for t, link, position in vehicle["points"]:
            frames.setdefault(t, []).append({"id": vehicle["id"], "link": link, "position": position})
    ordered = [{"t": t, "vehicles": sorted(frames[t], key=lambda v: v["id"])} for t in sorted(frames)]
    return {"speed": speed, "playbackIntervalSeconds": round(TRAJECTORY_STEP_SECONDS / speed, 3),
            "frameCount": len(ordered), "vehicleCount": len(trajectories), "frames": ordered}
