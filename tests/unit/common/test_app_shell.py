"""Shared skeleton (Naveen): the app starts, every page renders, errors share one shape."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tms.common import clock
from tms.common.errors import NotFoundError, register_handlers



class Body(BaseModel):
    n: int


PAGES = ["/", "/operator", "/detection", "/simulation", "/incidents", "/reports", "/admin"]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "<html" in response.text.lower()


def test_static_files_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_openapi_page_is_available(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_clock_can_be_frozen_and_advanced():
    start = clock.freeze(clock.now())
    assert clock.now() == start
    clock.advance(90)
    assert (clock.now() - start).total_seconds() == 90


def test_errors_use_one_shape():
    app = FastAPI()
    register_handlers(app)

    @app.get("/gone")
    def gone():
        raise NotFoundError("nothing here", code="not_found")

    @app.post("/body")
    def body(item: Body):
        return item

    test_client = TestClient(app)
    missing = test_client.get("/gone")
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found", "detail": "nothing here"}

    bad_json = test_client.post("/body", content="{oops", headers={"Content-Type": "application/json"})
    assert bad_json.status_code == 400
    assert bad_json.json()["error"] == "invalid_payload"

    bad_value = test_client.post("/body", json={"n": "text"})
    assert bad_value.status_code == 422
    assert bad_value.json()["error"] == "validation_failed"
    assert bad_value.json()["detail"][0]["field"] == "n"
