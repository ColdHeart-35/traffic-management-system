"""Tables owned by the Simulation Engine (Naveen)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class SimNetwork(Base):
    __tablename__ = "sim_networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    topology: Mapped[str] = mapped_column(Text)          # JSON: nodes, links, demand
    created_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


class SimRun(Base):
    __tablename__ = "sim_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("sim_networks.id"), index=True)
    params: Mapped[str] = mapped_column(Text)             # JSON
    metrics: Mapped[str] = mapped_column(Text)            # JSON
    trajectories: Mapped[str] = mapped_column(Text)       # JSON, sampled every few seconds
    created_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
