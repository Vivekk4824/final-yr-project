import math
import os
import uuid

from fastapi.testclient import TestClient
import pandas as pd
import pytest
from sqlalchemy import create_engine, make_url, text

from backend.application import app
from backend.core import context
from backend.recommendation.location_ranking import LocationRankingPolicy, apply_location_ranking
from backend.repositories import database as db
from backend.services import authentication, vendors


@pytest.fixture(params=["sqlite", "postgresql"])
def operational_database(request, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_HMAC_SECRET", "isolated-location-recommendation-test-secret")
    if request.param == "sqlite":
        yield tmp_path / "operational.db"
        return
    test_url = os.environ.get("VENDORMAP_TEST_POSTGRES_URL")
    if not test_url:
        pytest.skip("A disposable PostgreSQL instance was not supplied")
    engine = create_engine(test_url)
    schema = "location_test_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    try:
        url = make_url(test_url).update_query_dict({"options": f"-csearch_path={schema}"})
        yield url.render_as_string(hide_password=False)
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()


def test_additive_location_migration_keeps_old_profiles_and_supports_partial_updates(operational_database):
    database = operational_database
    db.initialize_database(database)
    vendor = vendors.register_vendor({"business_category": "food", "full_name": "Existing vendor",
                                      "preferred_locality": "Legacy locality"}, database)
    vendor_id = vendor["vendor_id"]
    with db.transaction(database) as connection:
        for column in db.VENDOR_LOCATION_COLUMNS:
            connection.execute(f"ALTER TABLE operational_vendors DROP COLUMN {column}")

    db.initialize_database(database)
    db.migrate_vendor_location_preferences(database)
    old = vendors.get_vendor_profile(vendor_id, database)
    assert old["application_vendor_id"] == vendor["application_vendor_id"]
    assert old["full_name"] == "Existing vendor"
    assert all(old[column] is None for column in db.VENDOR_LOCATION_COLUMNS)

    pin = {"preferred_latitude": 19.9960883, "preferred_longitude": 73.8003276, "preferred_radius_km": 3}
    vendors.update_vendor_profile(vendor_id, pin, database)
    saved = vendors.update_vendor_profile(vendor_id, {"preferred_language": "mr"}, database)
    assert {column: saved[column] for column in pin} == pin
    assert saved["preferred_locality"] == "Legacy locality"
    with pytest.raises(db.OperationalValidationError):
        vendors.update_vendor_profile(vendor_id, {"preferred_latitude": None}, database)
    cleared = vendors.update_vendor_profile(vendor_id, dict.fromkeys(pin), database)
    assert all(cleared[column] is None for column in pin)
    assert cleared["preferred_language"] == "mr"


def test_location_formula_ties_and_missing_distance(monkeypatch):
    scored = pd.DataFrame({
        "zone_id": ["C", "A", "B", "unmapped", "unscored"],
        "score": [50.0, 50, 50, 99, None],
        "original_mcda_score": [49.0, 48, 49, 99, None],
    })
    monkeypatch.setattr("backend.recommendation.location_ranking.reviewed_coordinates", lambda zones: pd.DataFrame(
        {"latitude": [0.0, 0, 0, None, 0], "longitude": [1.0, 1, 1, None, 0]}, index=zones.index,
    ))
    ranked = apply_location_ranking(scored, (0.0, 0.0), LocationRankingPolicy())
    assert ranked.zone_id.tolist() == ["B", "C", "A", "unmapped", "unscored"]
    assert ranked.iloc[0].distance_km == pytest.approx(111.195, abs=.001)
    assert ranked.iloc[0].personalized_score == pytest.approx(42.5 + 15 * math.exp(-111.195 / 3))
    assert pd.isna(ranked.iloc[3].distance_km)
    assert ranked.iloc[3:].personalized_score.isna().all()


def test_authenticated_ranking_radius_and_expansion_use_current_saved_profile(operational_database, monkeypatch):
    database = operational_database
    db.initialize_database(database)
    monkeypatch.setattr(context, "DATABASE_PATH", database)
    monkeypatch.setattr(context, "AUTH_TEST_BYPASS", False)
    monkeypatch.setenv("LOCATION_RANKING_EXPERIMENT", "true")
    monkeypatch.delenv("LOCATION_PROXIMITY_WEIGHT", raising=False)
    monkeypatch.setenv("LOCATION_PROXIMITY_DECAY_KM", "3")
    monkeypatch.setenv("BUSINESS_AWARE_MCDA_EXPERIMENT", "true")

    def session(preferences):
        vendor = vendors.register_vendor(preferences, database)
        with db.transaction(database) as connection:
            token, _ = authentication._create_session(connection, "VENDOR", vendor_id=vendor["vendor_id"])
        return vendor["vendor_id"], TestClient(app, cookies={authentication.SESSION_COOKIE_NAME: token})

    saved_profile = {"business_category": "food", "preferred_division": "Nashik East"}
    vendor_id, vendor_client = session(saved_profile)
    other_id, other_client = session({"business_category": "clothing", "preferred_division": "Satpur"})
    with vendor_client as first, other_client as second:
        route = f"/api/vendors/{vendor_id}"
        patch = first.patch(route, json={"preferred_latitude": 19.9960883, "preferred_longitude": 73.8003276,
                                        "preferred_radius_km": 1, "priority_profile": "COMMERCIAL",
                                        "market_preference": True})
        assert patch.status_code == 200, patch.text
        assert first.get(route).json()["preferred_radius_km"] == 1
        assert first.patch(route, json={"preferred_latitude": 91}).status_code == 422
        assert first.patch(route, json={"preferred_radius_km": 2}).status_code == 422
        assert second.patch(route, json={"preferred_radius_km": None}).status_code == 403
        assert second.post("/api/recommendations", json={"vendor_id": vendor_id}).status_code == 403

        def recommend(client, **body):
            response = client.post("/api/recommendations", json=body)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "private, no-store"
            return response.json()

        nearby = recommend(first, business="clothing", division="Satpur")
        assert nearby["recommendations"] == recommend(first)["recommendations"]
        assert nearby["selected_division"] == "Nashik East"
        assert nearby["priority_profile"] == "COMMERCIAL"
        assert nearby["preference_flags"]["market"]
        assert nearby["recommendations"]
        assert all(row["zone_division"] == "Nashik East" and row["distance_km"] <= 1 for row in nearby["recommendations"])
        for row in nearby["recommendations"]:
            assert row["requested_business_category"] == "food"
            assert row["personalized_score"] == pytest.approx(.85 * row["score"] + .15 * row["proximity_score"])
            assert row["ranking_reason"]

        other = recommend(second, vendor_id=other_id)
        assert other["selected_division"] == "Satpur" and not other["location_ranking"]["applied"]
        assert all(row["score"] == row["personalized_score"] and row["distance_km"] is None
                   for row in other["recommendations"])

        first.patch(route, json={"preferred_latitude": 19.98, "preferred_longitude": 73.60})
        few = recommend(first, vendor_id=vendor_id)
        assert few["count"] == 0 and few["location_ranking"]["can_expand"]
        expanded = recommend(first, vendor_id=vendor_id, expand_search=True)
        assert expanded["count"] == 3 and expanded["location_ranking"]["expanded"]
        assert first.get(route).json()["preferred_radius_km"] == 1
        assert {row["zone_id"] for row in few["remaining_recommendations"]} == {
            row["zone_id"] for row in expanded["recommendations"] + expanded["remaining_recommendations"]
        }
        assert expanded["eligible_unscorable_zones"]
        assert all(row["score"] is None and row["personalized_score"] is None for row in expanded["eligible_unscorable_zones"])
        assert all(row["zone_type"] == "FREE" and row["available_capacity"] > 0 for row in expanded["remaining_recommendations"])

        assert first.patch(route, json={"business_category": "clothing", "preferred_division": None}).status_code == 200
        citywide = recommend(first, vendor_id=vendor_id, expand_search=True)
        assert citywide["selected_division"] is None
        assert all(row["requested_business_category"] == "clothing" for row in citywide["recommendations"])
        assert recommend(second, vendor_id=other_id)["recommendations"] == other["recommendations"]

        monkeypatch.setenv("LOCATION_RANKING_EXPERIMENT", "false")
        monkeypatch.setenv("BUSINESS_AWARE_MCDA_EXPERIMENT", "false")
        baseline = recommend(first, vendor_id=vendor_id)
        assert baseline["count"] == 3 and not baseline["location_ranking"]["applied"]
        assert all(row["score"] == row["original_mcda_score"] == row["personalized_score"] for row in baseline["recommendations"])
