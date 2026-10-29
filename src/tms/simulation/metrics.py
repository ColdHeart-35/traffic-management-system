"""Simulation performance metrics (TMS-F-011): average delay, queue length and throughput."""
from __future__ import annotations

DISCLAIMER = ("Simulation results are estimates and do not replace formal traffic-engineering sign-off.")


def compute_metrics(result: dict) -> dict:
    """Turn the raw result of ``run_simulation`` into the metrics shown to the analyst."""
    duration = result["params"]["duration_seconds"]
    delays = result["delays"]
    queue = result["queue"]
    approach_links = max(1, queue["approachLinks"])
    avg_delay = sum(delays) / len(delays) if delays else 0.0
    avg_queue = (queue["sumQueued"] / max(1, queue["ticks"])) / approach_links
    return {
        "averageDelaySeconds": round(avg_delay, 2),
        "averageQueueLength": round(avg_queue, 2),     # vehicles waiting, per signalised approach
        "maxQueueLength": queue["maxQueue"],           # most vehicles queued on one approach at one time
        "throughputPerHour": round(result["vehiclesCompleted"] * 3600.0 / duration, 1),
        "vehiclesEntered": result["vehiclesEntered"],
        "vehiclesCompleted": result["vehiclesCompleted"],
        "vehiclesStillInNetwork": result["vehiclesInNetwork"],
        "durationSeconds": duration,
        "disclaimer": DISCLAIMER,
    }
