"""Per-lane vehicle counting and traffic density (TMS-F-007).

Counts are stored in time buckets (default one minute, set per intersection). The signal
controller reads ``get_density`` to decide green times.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.detection.models import TrafficCount

EPOCH = datetime(1970, 1, 1)


def bucket_start(timestamp: datetime, interval_seconds: int) -> datetime:
    seconds = int((timestamp - EPOCH).total_seconds())
    return EPOCH + timedelta(seconds=seconds - seconds % interval_seconds)


def record_count(db: Session, intersection_id: str, approach: str, lane: int, timestamp: datetime,
                 vehicle_class: str, count: int = 1) -> TrafficCount:
    cfg = config_service.get_intersection_config(db, intersection_id)
    start = bucket_start(timestamp, cfg["count_interval_seconds"])
    row = db.scalar(select(TrafficCount).where(
        TrafficCount.intersection_id == intersection_id, TrafficCount.approach == approach,
        TrafficCount.lane == lane, TrafficCount.interval_start == start,
        TrafficCount.vehicle_class == vehicle_class))
    if row is None:
        row = TrafficCount(intersection_id=intersection_id, approach=approach, lane=lane,
                           interval_start=start, vehicle_class=vehicle_class, count=0)
        db.add(row)
    row.count += count
    return row


def get_counts(db: Session, intersection_id: str, approach: str | None = None, lane: int | None = None,
               since: datetime | None = None, until: datetime | None = None) -> list[dict]:
    query = select(TrafficCount).where(TrafficCount.intersection_id == intersection_id)
    if approach:
        query = query.where(TrafficCount.approach == approach)
    if lane is not None:
        query = query.where(TrafficCount.lane == lane)
    if since:
        query = query.where(TrafficCount.interval_start >= since)
    if until:
        query = query.where(TrafficCount.interval_start < until)
    rows = db.scalars(query.order_by(TrafficCount.interval_start, TrafficCount.approach,
                                     TrafficCount.lane, TrafficCount.vehicle_class)).all()
    return [{"intersectionId": r.intersection_id, "approach": r.approach, "lane": r.lane,
             "intervalStart": r.interval_start.isoformat(), "vehicleClass": r.vehicle_class,
             "count": r.count} for r in rows]


def total_vehicles(db: Session, intersection_id: str, since: datetime | None = None,
                   until: datetime | None = None) -> int:
    query = select(func.coalesce(func.sum(TrafficCount.count), 0)).where(TrafficCount.intersection_id == intersection_id)
    if since:
        query = query.where(TrafficCount.interval_start >= since)
    if until:
        query = query.where(TrafficCount.interval_start < until)
    return int(db.scalar(query) or 0)


def get_density(db: Session, intersection_id: str, approach: str) -> float:
    """Vehicles per minute on ``approach`` over the latest window of stored counts."""
    cfg = config_service.get_intersection_config(db, intersection_id)
    latest = db.scalar(select(func.max(TrafficCount.interval_start)).where(
        TrafficCount.intersection_id == intersection_id))
    if latest is None:
        return 0.0
    window = timedelta(minutes=cfg["density_window_minutes"])
    end = latest + timedelta(seconds=cfg["count_interval_seconds"])
    total = db.scalar(select(func.coalesce(func.sum(TrafficCount.count), 0)).where(
        TrafficCount.intersection_id == intersection_id, TrafficCount.approach == approach,
        TrafficCount.interval_start >= end - window, TrafficCount.interval_start < end))
    return float(total or 0) / cfg["density_window_minutes"]


def approach_densities(db: Session, intersection_id: str) -> dict[str, float]:
    cfg = config_service.get_intersection_config(db, intersection_id)
    return {approach: round(get_density(db, intersection_id, approach), 3) for approach in cfg["approaches"]}
