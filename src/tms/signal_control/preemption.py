"""Emergency-vehicle preemption (TMS-F-004).

A validated request turns the approach corridor (the phase the approach belongs to) green and holds it
until the vehicle has passed or the hold time ends; then normal adaptive operation resumes.

Timing: the request takes effect at once (the current stage is cut short within one second). The
conflicting phase still shows its full yellow and all-red clearance, so green appears after at most
``yellow + all_red`` seconds. That clearance is a safety minimum and is not skipped (docs/deviations.md).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.common import clock
from tms.common.errors import CommandError
from tms.signal_control import audit, override
from tms.signal_control.controller import MANUAL, advance_state, get_or_create_state

DEFAULT_HOLD = 30
MIN_HOLD, MAX_HOLD = 15, 120
ACTOR = "emergency-vehicle"


def request_preemption(db: Session, intersection_id: str, approach: str, vehicle_id: str,
                       hold_seconds: int = DEFAULT_HOLD, now: datetime | None = None) -> dict:
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    if approach not in cfg["approaches"]:
        raise CommandError(f"approach must be one of {sorted(cfg['approaches'])}", code="invalid_approach")
    if not vehicle_id or len(vehicle_id) > 40:
        raise CommandError("vehicleId is required (up to 40 characters)", code="invalid_vehicle")
    if isinstance(hold_seconds, bool) or not isinstance(hold_seconds, int) or not MIN_HOLD <= hold_seconds <= MAX_HOLD:
        raise CommandError(f"holdSeconds must be between {MIN_HOLD} and {MAX_HOLD}", code="invalid_duration")
    phase = cfg["approaches"][approach]
    result = override.request_override(db, intersection_id, phase, hold_seconds, f"{ACTOR}:{vehicle_id}", now,
                                       command_source="preemption-channel", source="preemption",
                                       details={"approach": approach, "vehicleId": vehicle_id})
    state = get_or_create_state(db, intersection_id, now, cfg)
    clearance = 0 if (state.phase == phase and state.stage == "GREEN") else cfg["yellow"] + cfg["all_red"]
    return {"status": "applied", "preemptionId": "PRE-" + uuid.uuid4().hex[:10], "appliedAt": result["appliedAt"],
            "phase": phase, "until": result["until"], "greenWithinSeconds": clearance,
            "stage": state.stage}


def clear_preemption(db: Session, intersection_id: str, vehicle_id: str, now: datetime | None = None) -> dict:
    """The vehicle has cleared the intersection: resume normal operation."""
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    state = get_or_create_state(db, intersection_id, now, cfg)
    advance_state(db, state, cfg, now)
    if state.mode == MANUAL and state.control_source == "preemption":
        return override.clear_override(db, intersection_id, f"{ACTOR}:{vehicle_id}", now, "preemption-channel")
    db.commit()
    return {"status": "no_active_preemption", "mode": state.mode}
