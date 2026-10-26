"""Synthetic (mock) sensor data. A fixed seed always gives the same output.

Used by ``data/detection_samples/generate_feed.py`` (to post a live feed to the API) and by the
tests (to build the validation set and ground-truth counts).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from tms.detection.classifier import CLASSES, VehicleFeatures

# (length mean, length sd, width mean, width sd, height mean, height sd, has_windows)
_PROFILES = {
    "car": (4.3, 0.35, 1.8, 0.08, 1.5, 0.10, True),
    "two_wheeler": (2.0, 0.15, 0.8, 0.07, 1.3, 0.10, False),
    "bus": (11.0, 1.0, 2.5, 0.07, 3.1, 0.15, True),
    "truck": (8.5, 1.6, 2.5, 0.08, 3.3, 0.30, False),
}
CLASS_WEIGHTS = {"car": 0.62, "two_wheeler": 0.18, "truck": 0.12, "bus": 0.08}


def make_features(rng: random.Random, vehicle_class: str) -> VehicleFeatures:
    lm, ls, wm, ws, hm, hs, windows = _PROFILES[vehicle_class]
    return VehicleFeatures(
        length_m=round(max(1.2, rng.gauss(lm, ls)), 2),
        width_m=round(max(0.4, rng.gauss(wm, ws)), 2),
        height_m=round(max(0.8, rng.gauss(hm, hs)), 2),
        has_windows=windows,
    )


def validation_set(seed: int = 7, per_class: int = 250) -> list[tuple[VehicleFeatures, str]]:
    rng = random.Random(seed)
    rows = [(make_features(rng, cls), cls) for cls in CLASSES for _ in range(per_class)]
    rng.shuffle(rows)
    return rows


def generate_events(intersection_id: str = "INT-001", seed: int = 1, minutes: int = 15,
                    start: datetime | None = None, vehicles_per_minute: dict[str, int] | None = None,
                    pedestrian_every_minutes: int = 0, source_id: str = "SIM-CAM-1") -> list[dict]:
    """Build detection payloads (the body of POST /api/v1/detections) for ``minutes`` minutes.

    ``vehicles_per_minute`` maps approach -> vehicles each minute (default 6 per approach).
    Every vehicle is one event with ``count`` 1; the ground truth is simply the number of events.
    """
    rng = random.Random(seed)
    start = start or datetime(2026, 10, 19, 9, 0, 0)
    rates = vehicles_per_minute or {"N": 6, "S": 6, "E": 6, "W": 6}
    classes = list(CLASS_WEIGHTS)
    weights = [CLASS_WEIGHTS[c] for c in classes]
    events: list[dict] = []
    for minute in range(minutes):
        for approach, n in rates.items():
            for _ in range(n):
                cls = rng.choices(classes, weights)[0]
                f = make_features(rng, cls)
                stamp = start + timedelta(minutes=minute, seconds=rng.randint(0, 59))
                events.append({
                    "intersectionId": intersection_id,
                    "timestamp": stamp.isoformat() + "Z",
                    "sourceId": source_id,
                    "detectionType": "vehicle",
                    "class": cls,
                    "count": 1,
                    "confidence": round(rng.uniform(0.85, 0.99), 2),
                    "approach": approach,
                    "lane": rng.randint(1, 2),
                })
        if pedestrian_every_minutes and minute % pedestrian_every_minutes == 0 and minute > 0:
            events.append({
                "intersectionId": intersection_id,
                "timestamp": (start + timedelta(minutes=minute, seconds=30)).isoformat() + "Z",
                "sourceId": "SIM-XWALK-1",
                "detectionType": "pedestrian",
                "count": 1,
                "confidence": 0.99,
            })
    events.sort(key=lambda e: e["timestamp"])
    return events
