"""Tables owned by the Admin module (Roshini): users, login tokens, security log, config history."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)  # used in Sprint 2 (PRJ-SR-002)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class SecurityLog(Base):
    __tablename__ = "security_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    username: Mapped[str | None] = mapped_column(String(60), nullable=True)
    event: Mapped[str] = mapped_column(String(60))
    details: Mapped[str] = mapped_column(Text, default="")


class IntersectionConfigHistory(Base):
    __tablename__ = "intersection_config_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer)
    config: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
