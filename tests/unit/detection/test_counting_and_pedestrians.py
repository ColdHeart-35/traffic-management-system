"""Per-lane counting, density and pedestrian requests (Likhita): TMS-F-007, TMS-F-008."""
from __future__ import annotations

from datetime import datetime

from tms.admin import config_service
from tms.detection import counter, pedestrian
from tms.detection.api import DetectionIn, ingest_detection
from tms.detection.synthetic import generate_events

from tests.conftest import START


def feed(session, events: list[dict]) -> None:
    for event in events:
        ingest_detection(session, DetectionIn(**event))


def vehicle(approach="N", lane=1, at="2026-10-19T09:00:10Z", cls="car", count=1) -> dict:
    return {"intersectionId": "INT-001", "timestamp": at, "sourceId": "cam-1", "detectionType": "vehicle",
            "class": cls, "count": count, "confidence": 0.95, "approach": approach, "lane": lane}


def test_TC_VDC_02_counts_match_the_ground_truth_over_15_minutes(session):
    events = generate_events(seed=3, minutes=15, start=START)
    truth = len([e for e in events if e["detectionType"] == "vehicle"])
    feed(session, events)
    session.commit()
    counted = counter.total_vehicles(session, "INT-001")
    assert truth == 15 * 24
    assert abs(counted - truth) / truth <= 0.05       # the requirement allows 5%
    assert counted == truth                            # and this implementation is exact


def test_counts_are_kept_per_approach_lane_and_class(session):
    feed(session, [vehicle("N", 1), vehicle("N", 1), vehicle("N", 2), vehicle("E", 1, cls="bus")])
    rows = counter.get_counts(session, "INT-001")
    by_key = {(r["approach"], r["lane"], r["vehicleClass"]): r["count"] for r in rows}
    assert by_key == {("N", 1, "car"): 2, ("N", 2, "car"): 1, ("E", 1, "bus"): 1}
    assert [r["count"] for r in counter.get_counts(session, "INT-001", approach="E")] == [1]
    assert [r["count"] for r in counter.get_counts(session, "INT-001", lane=2)] == [1]


def test_count_field_adds_several_vehicles_at_once(session):
    feed(session, [vehicle(count=4), vehicle(count=3)])
    assert counter.total_vehicles(session, "INT-001") == 7


def test_bucket_start_rounds_down_to_the_interval():
    stamp = datetime(2026, 10, 19, 9, 0, 59)
    assert counter.bucket_start(stamp, 60) == datetime(2026, 10, 19, 9, 0, 0)
    assert counter.bucket_start(stamp, 30) == datetime(2026, 10, 19, 9, 0, 30)


def test_the_interval_is_configurable_per_intersection(session):
    feed(session, [vehicle(at="2026-10-19T09:00:10Z"), vehicle(at="2026-10-19T09:00:40Z")])
    assert len(counter.get_counts(session, "INT-001")) == 1          # one 60-second bucket
    config_service.update_intersection_config(session, "INT-001", {"count_interval_seconds": 30})
    feed(session, [vehicle(at="2026-10-19T09:05:10Z"), vehicle(at="2026-10-19T09:05:40Z")])
    later = counter.get_counts(session, "INT-001", since=datetime(2026, 10, 19, 9, 5))
    assert len(later) == 2                                            # two 30-second buckets


def test_density_is_vehicles_per_minute_over_the_window(session):
    # 10 vehicles on N spread over 5 minutes, window of 5 minutes -> 2 vehicles per minute
    feed(session, [vehicle("N", at=f"2026-10-19T09:0{m}:10Z") for m in range(5) for _ in range(2)])
    assert counter.get_density(session, "INT-001", "N") == 2.0
    assert counter.get_density(session, "INT-001", "S") == 0.0
    assert counter.approach_densities(session, "INT-001") == {"N": 2.0, "S": 0.0, "E": 0.0, "W": 0.0}


def test_density_is_zero_without_data(session):
    assert counter.get_density(session, "INT-001", "N") == 0.0


def test_pedestrian_request_is_pending_until_served(session):
    assert not pedestrian.has_pending(session, "INT-001")
    pedestrian.request_crossing(session, "INT-001", START, crosswalk="N")
    session.commit()
    assert pedestrian.has_pending(session, "INT-001")
    assert len(pedestrian.get_pedestrian_requests(session, "INT-001")) == 1
    assert pedestrian.mark_served(session, "INT-001", START) == 1
    assert not pedestrian.has_pending(session, "INT-001")
    assert pedestrian.get_pedestrian_requests(session, "INT-001") == []


def test_pedestrian_detection_creates_a_request(session):
    feed(session, [{"intersectionId": "INT-001", "timestamp": "2026-10-19T09:00:30Z", "sourceId": "xwalk-1",
                    "detectionType": "pedestrian", "count": 1, "confidence": 0.99}])
    assert len(pedestrian.get_pedestrian_requests(session, "INT-001")) == 1
