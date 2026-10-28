"""Admin and sign-in endpoints (Roshini)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.admin.models import SecurityLog, User
from tms.common.db import get_db

router = APIRouter(prefix="/api/v1", tags=["admin"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class UserIn(BaseModel):
    username: str
    password: str
    role: str


class RoleIn(BaseModel):
    role: str


class IntersectionIn(BaseModel):
    id: str
    name: str = ""
    config: dict | None = None


class ConfigIn(BaseModel):
    changes: dict


# ---------- sign in ----------

@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    token, user = rbac.login(db, body.username, body.password)
    return {"token": token, "username": user.username, "role": user.role}


@router.get("/auth/me")
def me(user: rbac.CurrentUser = Depends(rbac.require_role())):
    return {"username": user.username, "role": user.role, "permissions": rbac.ROLE_PERMISSIONS[user.role]}


# ---------- intersections ----------

@router.get("/intersections")
def intersections(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role())):
    return config_service.list_intersections(db)


@router.get("/admin/intersections/{intersection_id}/config")
def get_config(intersection_id: str, db: Session = Depends(get_db),
               _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.get_intersection_config(db, intersection_id)


@router.post("/admin/intersections", status_code=201)
def create_intersection(body: IntersectionIn, db: Session = Depends(get_db),
                        user: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.create_intersection(db, body.id, body.name, body.config, actor=user.username)


@router.put("/admin/intersections/{intersection_id}/config")
def update_config(intersection_id: str, body: ConfigIn, db: Session = Depends(get_db),
                  user: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.update_intersection_config(db, intersection_id, body.changes, actor=user.username)


@router.get("/admin/intersections/{intersection_id}/config/history")
def config_history(intersection_id: str, db: Session = Depends(get_db),
                   _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.config_history(db, intersection_id)


# ---------- users and roles ----------

@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    rows = db.scalars(select(User).order_by(User.username)).all()
    return [{"username": u.username, "role": u.role, "active": u.active} for u in rows]


@router.post("/admin/users", status_code=201)
def add_user(body: UserIn, db: Session = Depends(get_db),
             _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    user = rbac.create_user(db, body.username, body.password, body.role)
    return {"username": user.username, "role": user.role}


@router.put("/admin/users/{username}/role")
def change_role(username: str, body: RoleIn, db: Session = Depends(get_db),
                _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    user = rbac.set_user_role(db, username, body.role)
    return {"username": user.username, "role": user.role}


@router.get("/admin/roles")
def roles(_: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return rbac.ROLE_PERMISSIONS


@router.get("/admin/security-log")
def security_log(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db),
                 _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    rows = db.scalars(select(SecurityLog).order_by(SecurityLog.id.desc()).limit(limit)).all()
    return [{"timestamp": r.timestamp.isoformat(), "user": r.username, "event": r.event, "details": r.details}
            for r in rows]
