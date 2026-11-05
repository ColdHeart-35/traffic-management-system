"""Intersection configuration (Roshini): TMS-F-019 validated, versioned, applied without a restart."""
from __future__ import annotations

import pytest

from tms.admin import config_service
from tms.common.config import DEFAULT_INTERSECTION_CONFIG
from tms.common.errors import ValidationFailure

URL = "/api/v1/admin/intersections/INT-001/config"


def test_TC_Adm_02_change_is_validated_versioned_and_applied_without_restart(client, admin_h, session):
    before = client.get(URL, headers=admin_h).json()
    assert before["version"] == 1 and before["min_green"] == 10

    saved = client.put(URL, headers=admin_h, json={"changes": {"min_green": 12, "max_green": 50}})
    assert saved.status_code == 200
    assert saved.json()["version"] == 2

    # applied without a restart: same running app, other modules read the new value at once
    assert config_service.get_intersection_config(session, "INT-001")["max_green"] == 50
    assert client.get(URL, headers=admin_h).json()["min_green"] == 12


def test_invalid_change_is_rejected_and_nothing_changes(client, admin_h):
    bad = client.put(URL, headers=admin_h, json={"changes": {"max_green": 8}})
    assert bad.status_code == 422
    assert bad.json()["error"] == "validation_failed"
    assert client.get(URL, headers=admin_h).json()["version"] == 1


def test_cycle_that_cannot_hold_the_minimum_greens_is_rejected(client, admin_h):
    bad = client.put(URL, headers=admin_h, json={"changes": {"min_green": 30, "cycle_seconds": 40}})
    assert bad.status_code == 422
    assert "too short" in str(bad.json()["detail"])


def test_unknown_setting_is_rejected(client, admin_h):
    assert client.put(URL, headers=admin_h, json={"changes": {"turbo_mode": 1}}).status_code == 422


def test_history_keeps_every_version_newest_first(client, admin_h):
    client.put(URL, headers=admin_h, json={"changes": {"yellow": 4}})
    client.put(URL, headers=admin_h, json={"changes": {"yellow": 5}})
    history = client.get(URL + "/history", headers=admin_h).json()
    assert [row["version"] for row in history] == [3, 2, 1]
    assert history[0]["changedBy"] == "admin" and history[0]["config"]["yellow"] == 5
    assert history[-1]["config"]["yellow"] == 3


def test_unknown_intersection_is_404(client, admin_h):
    assert client.get("/api/v1/admin/intersections/NOPE/config", headers=admin_h).status_code == 404


def test_new_intersection_can_be_added(client, admin_h, operator_h):
    created = client.post("/api/v1/admin/intersections", headers=admin_h, json={"id": "INT-002", "name": "Second"})
    assert created.status_code == 201 and created.json()["version"] == 1
    listed = client.get("/api/v1/intersections", headers=operator_h).json()
    assert [row["id"] for row in listed] == ["INT-001", "INT-002"]


def test_duplicate_or_badly_named_intersection_is_rejected(client, admin_h):
    assert client.post("/api/v1/admin/intersections", headers=admin_h, json={"id": "INT-001"}).status_code == 409
    assert client.post("/api/v1/admin/intersections", headers=admin_h, json={"id": "has space"}).status_code == 400


def test_default_configuration_is_valid():
    assert config_service.validate_config(dict(DEFAULT_INTERSECTION_CONFIG)) == DEFAULT_INTERSECTION_CONFIG


def test_booleans_are_not_accepted_as_numbers():
    config = dict(DEFAULT_INTERSECTION_CONFIG, yellow=True)
    with pytest.raises(ValidationFailure):
        config_service.validate_config(config)
