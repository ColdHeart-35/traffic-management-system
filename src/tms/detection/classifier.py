"""Vehicle classification (TMS-F-006).

Camera and sensor hardware does not exist in this project, so the sensor input is a set of
measured features (length, width, height, whether the side has passenger windows). A rule
based classifier turns them into one of four classes. It is checked against the synthetic
validation set in ``data/detection_samples/validation_set.csv`` (target: at least 90%).
"""
from __future__ import annotations

from dataclasses import dataclass

CLASSES = ("car", "bus", "truck", "two_wheeler")


@dataclass(frozen=True)
class VehicleFeatures:
    length_m: float
    width_m: float
    height_m: float
    has_windows: bool = False


def classify_vehicle(features: VehicleFeatures) -> str:
    """Return one of CLASSES for the measured features."""
    length, width, height = features.length_m, features.width_m, features.height_m
    if length < 2.9 and width < 1.3:
        return "two_wheeler"
    if length >= 7.5 and features.has_windows:
        return "bus"
    if length >= 5.9 or (height >= 2.5 and not features.has_windows):
        return "truck"
    return "car"


def accuracy(rows: list[tuple[VehicleFeatures, str]]) -> float:
    """Share of rows whose predicted class equals the true class."""
    if not rows:
        return 0.0
    correct = sum(1 for features, truth in rows if classify_vehicle(features) == truth)
    return correct / len(rows)
