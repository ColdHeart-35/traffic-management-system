"""POST /api/v1/detections and the read endpoints (Likhita), as in SAD section 4.3."""
from __future__ import annotations

URL = "/api/v1/detections"


def body(**changes) -> dict:
    event = {"intersectionId": "INT-001", "timestamp": "2026-10-19T09:00:05Z", "sourceId": "cam-N1",
             "detectionType": "vehicle", "class": "car", "count": 1, "confidence": 0.93, "approach": "N", "lane": 1}
    event.update(changes)
    return {k: v for k, v in event.items() if v is not None}


def test_valid_detection_is_accepted(client, sensor_h):
    response = client.post(URL, json=body(), headers=sensor_h)
    assert response.status_code == 201
    assert response.json()["status"] == "accepted"
    assert response.json()["eventId"].startswith("EVT-")


def test_sensor_key_is_required(client):
    assert client.post(URL, json=body()).status_code == 401
    assert client.post(URL, json=body(), headers={"X-API-Key": "wrong"}).status_code == 403


def test_a_signed_in_user_without_the_sensor_key_cannot_post(client, operator_h):
    assert client.post(URL, json=body(), headers=operator_h).status_code == 401


def test_malformed_json_is_400(client, sensor_h):
    response = client.post(URL, content="{not json", headers={**sensor_h, "Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_payload"


def test_validation_failures_are_422(client, sensor_h):
    for bad in (body(confidence=1.5), body(detectionType="boat"), body(count=0), body(approach=None),
                body(lane=None), body(**{"class": None}), body(timestamp="yesterday")):
        assert client.post(URL, json=bad, headers=sensor_h).status_code == 422, bad


def test_approach_must_exist_at_the_intersection(client, sensor_h):
    response = client.post(URL, json=body(approach="Q"), headers=sensor_h)
    assert response.status_code == 422


def test_unknown_intersection_is_404(client, sensor_h):
    response = client.post(URL, json=body(intersectionId="NOPE"), headers=sensor_h)
    assert response.status_code == 404
    assert response.json()["error"] == "intersection_not_found"


def test_features_are_classified_when_no_class_is_given(client, sensor_h, operator_h):
    features = {"length_m": 11.0, "width_m": 2.5, "height_m": 3.1, "has_windows": True}
    response = client.post(URL, json=body(**{"class": None, "features": features}), headers=sensor_h)
    assert response.status_code == 201
    counts = client.get("/api/v1/detections/counts", params={"intersectionId": "INT-001"}, headers=operator_h).json()
    assert [(row["vehicleClass"], row["count"]) for row in counts] == [("bus", 1)]


def test_counts_and_density_endpoints_need_sign_in(client, sensor_h, operator_h, analyst_h):
    client.post(URL, json=body(), headers=sensor_h)
    params = {"intersectionId": "INT-001"}
    assert client.get("/api/v1/detections/counts", params=params).status_code == 401
    assert client.get("/api/v1/detections/counts", params=params, headers=analyst_h).status_code == 200
    density = client.get("/api/v1/intersections/INT-001/density", headers=operator_h).json()
    assert density["vehiclesPerMinute"]["N"] == 0.2          # 1 vehicle over the 5-minute window
    assert client.get("/api/v1/intersections/NOPE/density", headers=operator_h).status_code == 404


def test_pedestrian_requests_endpoint(client, sensor_h, operator_h):
    ped = body(detectionType="pedestrian", approach=None, lane=None, **{"class": None})
    assert client.post(URL, json=ped, headers=sensor_h).status_code == 201
    listed = client.get("/api/v1/intersections/INT-001/pedestrian-requests", headers=operator_h).json()
    assert len(listed) == 1
