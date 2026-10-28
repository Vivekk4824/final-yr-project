from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.core import context
from backend.decision_policy import derive_mcda_weights
from backend.mcda_engine import recommend
from backend.repositories.database import connect, initialize_database, transaction, utc_now
from backend.services.capacity_analysis import capacity_pressure_summary, zone_capacity_analysis
from backend.services.relocation_recommendations import relocation_recommendations
from backend.services.vendors import get_vendor_profile


def insert_association(db, vendor_id, zone_id, category="food"):
    now = utc_now()
    db.execute(
        """INSERT INTO historical_vendor_zone_associations
           (vendor_id, matched_zone_id, candidate_zone_ids_json, original_location_text,
            location_text_english, recorded_division, business_category, match_status,
            evidence_types_json, matched_landmark, source_provenance, algorithm_version,
            review_status, reviewed_by, reviewed_at, review_notes, created_at, updated_at)
           VALUES (?, ?, '[]', 'source place', 'Source Place', 'Nashik East', ?,
                   'AUTO_MATCHED', '["DISTINCTIVE_EXACT_LANDMARK"]', 'Source Place',
                   'test fixture', 'test-v1', 'UNREVIEWED', NULL, NULL, NULL, ?, ?)""",
        (vendor_id, zone_id, category, now, now),
    )


def test_capacity_separates_active_allocations_from_historical_planning_load(tmp_path):
    database = tmp_path / "capacity.db"
    initialize_database(database)
    db = connect(database)
    try:
        pressure_row = db.execute(
            "SELECT zone_id, official_capacity FROM zone_live_status WHERE official_capacity IS NOT NULL AND zone_id != 'NE_F_001' ORDER BY official_capacity, zone_id LIMIT 1"
        ).fetchone()
        pressure_zone, pressure_capacity = pressure_row["zone_id"], pressure_row["official_capacity"]
        unknown_zone = db.execute(
            "SELECT zone_id FROM zone_live_status WHERE official_capacity IS NULL ORDER BY zone_id LIMIT 1"
        ).fetchone()["zone_id"]
    finally:
        db.close()
    now = utc_now()
    with transaction(database) as db:
        insert_association(db, "HIST_ACTIVE", "NE_F_001")
        insert_association(db, "HIST_ACTIVE_ELSEWHERE", "NE_F_001")
        insert_association(db, "HIST_UNALLOCATED", "NE_F_001", "vegetable_fruit")
        for index in range(pressure_capacity + 1):
            insert_association(db, f"HIST_PRESSURE_{index}", pressure_zone)
        db.execute(
            """INSERT INTO allocation_requests
               (request_id, vendor_id, zone_id, request_type, status, created_at, updated_at, reviewed_at, reviewed_by)
               VALUES ('REQ_CAPACITY', 'HIST_ACTIVE', 'NE_F_001', 'NEW_ALLOCATION', 'APPROVED', ?, ?, ?, 'admin')""",
            (now, now, now),
        )
        db.execute(
            """INSERT INTO allocation_requests
               (request_id, vendor_id, zone_id, request_type, status, created_at, updated_at, reviewed_at, reviewed_by)
               VALUES ('REQ_ELSEWHERE', 'HIST_ACTIVE_ELSEWHERE', 'NE_F_002', 'NEW_ALLOCATION', 'APPROVED', ?, ?, ?, 'admin')""",
            (now, now, now),
        )
        db.execute(
            """INSERT INTO allocations
               (allocation_id, vendor_id, zone_id, request_id, status, allocated_at, approved_by, created_at, updated_at)
               VALUES ('ALLOC_ELSEWHERE', 'HIST_ACTIVE_ELSEWHERE', 'NE_F_002', 'REQ_ELSEWHERE', 'ACTIVE', ?, 'admin', ?, ?)""",
            (now, now, now),
        )
        db.execute(
            """INSERT INTO allocations
               (allocation_id, vendor_id, zone_id, request_id, status, allocated_at, approved_by, created_at, updated_at)
               VALUES ('ALLOC_CAPACITY', 'HIST_ACTIVE', 'NE_F_001', 'REQ_CAPACITY', 'ACTIVE', ?, 'admin', ?, ?)""",
            (now, now, now),
        )

    zones = zone_capacity_analysis(database)
    target = zones["NE_F_001"]
    assert target["operational_occupancy"] == 1
    assert target["accepted_historical_association_count"] == 3
    assert target["historical_planning_count"] == 1
    assert target["planning_load"] == 2
    assert target["operational_available"] == target["listed_official_capacity"] - 1
    assert target["planning_available"] == target["listed_official_capacity"] - 2
    assert target["planning_available"] >= 0
    assert zones["NE_F_002"]["operational_occupancy"] == 1
    assert zones[pressure_zone]["planning_available"] == 0
    assert zones[pressure_zone]["planning_overcapacity"] == 1
    assert zones[unknown_zone]["operational_available"] is None
    assert zones[unknown_zone]["planning_available"] is None
    assert capacity_pressure_summary(database)["zone_count"] == 308


def test_relocation_uses_mcda_order_with_nearby_first_and_writes_nothing(tmp_path, monkeypatch):
    database = tmp_path / "relocation.db"
    initialize_database(database)
    vendor_id, source_zone = "V2024_00033", "NE_F_014"
    with transaction(database) as db:
        insert_association(db, vendor_id, source_zone, "vegetable_fruit")
    profile = get_vendor_profile(vendor_id, database_path=database)
    weights = derive_mcda_weights(profile)["final_weights"]
    baseline = recommend(profile["business_category"], profile["preferred_division"] or "", vendor_id,
                         top_n=5, use_live_status=True, database_path=database,
                         factor_weights=weights, include_all=True).attrs["all_candidates"]
    scoreable = baseline.loc[baseline.score.notna() & baseline.zone_id.ne(source_zone)]
    first, second = scoreable.iloc[0], scoreable.iloc[1]
    locations = {
        source_zone: {"easting": 0.0, "northing": 0.0, "location_source": "MANUAL_PROVISIONAL"},
        first.zone_id: {"easting": 2_500.0, "northing": 0.0, "location_source": "MANUAL_PROVISIONAL"},
        second.zone_id: {"easting": 1_000.0, "northing": 0.0, "location_source": "MANUAL_PROVISIONAL"},
    }
    monkeypatch.setattr("backend.services.relocation_recommendations.resolve_zone_locations", lambda _: locations)
    db = connect(database)
    try:
        before = db.execute("SELECT COUNT(*) AS total FROM allocations").fetchone()["total"]
    finally:
        db.close()
    result = relocation_recommendations(vendor_id, database_path=database)
    assert [item["zone_id"] for item in result["recommendations"][:2]] == [first.zone_id, second.zone_id]
    assert result["recommendations"][0]["mcda_score"] == pytest.approx(float(first.score))
    assert result["recommendations"][0]["distance_m"] == 2_500.0
    assert all(item["zone_type"] == "FREE" for item in result["recommendations"])
    assert all(item["operational_available"] is None or item["operational_available"] > 0 for item in result["recommendations"])
    assert result["source_type"] == "ACCEPTED_HISTORICAL_ASSOCIATION"
    assert result["model_version"] == "manual-142-v2"
    db = connect(database)
    try:
        assert db.execute("SELECT COUNT(*) AS total FROM allocations").fetchone()["total"] == before
        assert db.execute("SELECT COUNT(*) AS total FROM allocation_requests").fetchone()["total"] == 0
    finally:
        db.close()
    now = utc_now()
    active_zone = "NE_F_001"
    locations[active_zone] = {"easting": 500.0, "northing": 0.0, "location_source": "MANUAL_PROVISIONAL"}
    with transaction(database) as db:
        db.execute(
            """INSERT INTO allocation_requests
               (request_id, vendor_id, zone_id, request_type, status, created_at, updated_at, reviewed_at, reviewed_by)
               VALUES ('REQ_RELOCATION_SOURCE', ?, ?, 'NEW_ALLOCATION', 'APPROVED', ?, ?, ?, 'admin')""",
            (vendor_id, active_zone, now, now, now),
        )
        db.execute(
            """INSERT INTO allocations
               (allocation_id, vendor_id, zone_id, request_id, status, allocated_at, approved_by, created_at, updated_at)
               VALUES ('ALLOC_RELOCATION_SOURCE', ?, ?, 'REQ_RELOCATION_SOURCE', 'ACTIVE', ?, 'admin', ?, ?)""",
            (vendor_id, active_zone, now, now, now),
        )
    active_source_result = relocation_recommendations(vendor_id, database_path=database)
    assert active_source_result["source_zone_id"] == active_zone
    assert active_source_result["source_type"] == "ACTIVE_APPROVED_ALLOCATION"
    assert active_zone not in {item["zone_id"] for item in active_source_result["recommendations"]}
    db = connect(database)
    try:
        active = db.execute(
            "SELECT zone_id FROM allocations WHERE vendor_id = ? AND status = 'ACTIVE'", (vendor_id,)
        ).fetchone()
        assert active["zone_id"] == active_zone
    finally:
        db.close()


def test_planning_endpoints_are_admin_only_and_review_mutation_is_removed(tmp_path, monkeypatch):
    database = tmp_path / "api.db"
    initialize_database(database)
    monkeypatch.setattr(context, "DATABASE_PATH", database)
    monkeypatch.setattr(context, "AUTH_TEST_BYPASS", False)
    with TestClient(app) as client:
        assert client.get("/api/admin/capacity-pressure").status_code == 401
        assert client.get("/api/admin/vendors/V2024_00033/relocation-recommendations").status_code == 401
        assert client.patch("/api/admin/vendors/V2024_00033/historical-association", json={}).status_code in {404, 405}
