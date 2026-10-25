"""Pedestrian crosswalk requests (TMS-F-008).

A crosswalk push-button or sensor creates a pending request. The signal controller serves it
at the next all-red moment by running a pedestrian stage, which happens within one cycle.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tms.common import clock
from tms.detection.models import PedestrianRequest


def request_crossing(db: Session, intersection_id: str, timestamp: datetime | None = None,
                     crosswalk: str | None = None) -> PedestrianRequest:
    row = PedestrianRequest(intersection_id=intersection_id, crosswalk=crosswalk,
                            requested_at=timestamp or clock.now(), status="pending")
    db.add(row)
    return row


def has_pending(db: Session, intersection_id: str) -> bool:
    db.flush()
    return db.scalar(select(PedestrianRequest.id).where(
        PedestrianRequest.intersection_id == intersection_id,
        PedestrianRequest.status == "pending").limit(1)) is not None


def get_pedestrian_requests(db: Session, intersection_id: str) -> list[dict]:
    """Pending crosswalk requests, oldest first."""
    rows = db.scalars(select(PedestrianRequest).where(
        PedestrianRequest.intersection_id == intersection_id,
        PedestrianRequest.status == "pending").order_by(PedestrianRequest.requested_at)).all()
    return [{"id": r.id, "crosswalk": r.crosswalk, "requestedAt": r.requested_at.isoformat()} for r in rows]


def mark_served(db: Session, intersection_id: str, at: datetime) -> int:
    db.flush()
    result = db.execute(update(PedestrianRequest).where(
        PedestrianRequest.intersection_id == intersection_id, PedestrianRequest.status == "pending"
    ).values(status="served", served_at=at))
    return result.rowcount or 0
