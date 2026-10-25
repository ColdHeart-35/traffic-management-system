"""Vehicle classification and the synthetic feed (Likhita): TMS-F-006."""
from __future__ import annotations

import csv
from pathlib import Path

from tms.detection.classifier import CLASSES, VehicleFeatures, accuracy, classify_vehicle
from tms.detection.synthetic import generate_events, validation_set

CSV = Path(__file__).resolve().parents[3] / "data" / "detection_samples" / "validation_set.csv"


def test_TC_VDC_01_classification_accuracy_is_at_least_90_percent():
    assert accuracy(validation_set()) >= 0.90


def test_every_class_is_recognised_most_of_the_time():
    rows = validation_set()
    for cls in CLASSES:
        of_class = [(f, t) for f, t in rows if t == cls]
        assert accuracy(of_class) >= 0.80, cls


def test_typical_vehicles():
    assert classify_vehicle(VehicleFeatures(4.3, 1.8, 1.5, True)) == "car"
    assert classify_vehicle(VehicleFeatures(2.0, 0.8, 1.3, False)) == "two_wheeler"
    assert classify_vehicle(VehicleFeatures(11.0, 2.5, 3.1, True)) == "bus"
    assert classify_vehicle(VehicleFeatures(8.5, 2.5, 3.3, False)) == "truck"


def test_boundary_values_do_not_crash_and_stay_in_the_class_list():
    for length in (0.5, 2.89, 2.9, 5.89, 5.9, 7.49, 7.5, 20.0):
        assert classify_vehicle(VehicleFeatures(length, 2.0, 2.0, True)) in CLASSES


def test_accuracy_of_nothing_is_zero():
    assert accuracy([]) == 0.0


def test_validation_csv_file_reaches_the_same_accuracy():
    with CSV.open() as handle:
        rows = [(VehicleFeatures(float(r["length_m"]), float(r["width_m"]), float(r["height_m"]),
                                 r["has_windows"] == "1"), r["label"]) for r in csv.DictReader(handle)]
    assert len(rows) >= 1000
    assert accuracy(rows) >= 0.90


def test_same_seed_gives_the_same_feed_and_a_new_seed_changes_it():
    assert generate_events(seed=5, minutes=3) == generate_events(seed=5, minutes=3)
    assert generate_events(seed=5, minutes=3) != generate_events(seed=6, minutes=3)


def test_feed_has_the_requested_volume_and_pedestrians():
    events = generate_events(minutes=10, vehicles_per_minute={"N": 3, "S": 2, "E": 1, "W": 0},
                             pedestrian_every_minutes=5)
    vehicles = [e for e in events if e["detectionType"] == "vehicle"]
    assert len(vehicles) == 10 * 6
    assert len([e for e in events if e["detectionType"] == "pedestrian"]) == 1  # minute 5 (minute 0 is skipped)
