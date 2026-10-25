"""Tables owned by the Detection module (Likhita)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_id: Mapped[str] = mapped_column(String(60))
    detection_type: Mapped[str] = mapped_column(String(20))        # vehicle | pedestrian
    vehicle_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float)
    approach: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


class TrafficCount(Base):
    """Vehicles per approach, lane, class and time interval (TMS-F-007)."""

    __tablename__ = "traffic_counts"
    __table_args__ = (
        UniqueConstraint("intersection_id", "approach", "lane", "interval_start", "vehicle_class",
                         name="uq_traffic_counts_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    approach: Mapped[str] = mapped_column(String(10))
    lane: Mapped[int] = mapped_column(Integer)
    interval_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    vehicle_class: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer, default=0)


class PedestrianRequest(Base):
    __tablename__ = "pedestrian_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    crosswalk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | served
    served_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
