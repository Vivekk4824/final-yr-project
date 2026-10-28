import csv
import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application import app
from backend.core import context
from backend.core.data_paths import dataset_path
from backend.repositories.database import connect, initialize_database
from backend.services.historical_associations import (
    association_map,
    normalize_location,
    persist_reconciliation,
    reconcile_historical_associations,
    review_association,
    zone_association_summary,
)


@pytest.fixture(scope="module")
def reconciled_workspace(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("historical-associations") / "operational.db"
    initialize_database(database_path)
    connection = connect(database_path)
    try:
        before = {
            "allocations": connection.execute("SELECT COUNT(*) AS total FROM allocations").fetchone()["total"],
            "slots": connection.execute("SELECT COUNT(*) AS total FROM pilot_slots").fetchone()["total"],
        }
    finally:
        connection.close()
    reconciliation = reconcile_historical_associations(database_path)
    return database_path, reconciliation, before


def test_normalization_handles_unicode_punctuation_and_abbreviations():
    assert normalize_location("  CBS Rd. ") == "cbs road"
    assert normalize_location("Market—Chowk") == "market chowk"
    assert normalize_location("पंचवटी  चौक") == "पंचवटी चौक"


def test_all_historical_vendors_are_classified_once(reconciled_workspace):
    _, reconciliation, _ = reconciled_workspace
    rows = reconciliation["results"]
    assert len(rows) == 7_259
    assert len({row["vendor_id"] for row in rows}) == 7_259
    assert Counter(row["match_status"] for row in rows) == {
        "AUTO_MATCHED": 1_671,
        "REVIEW_REQUIRED": 5_587,
        "UNMATCHED": 1,
    }
    with Path(dataset_path("official_zones")).open(newline="", encoding="utf-8-sig") as source:
        official_ids = {row["zone_id"] for row in csv.DictReader(source)}
    assert all(not row["matched_zone_id"] or row["matched_zone_id"] in official_ids for row in rows)
    assert all(len(row["candidate_zone_ids"]) <= 3 for row in rows)


def test_ambiguous_market_names_are_not_auto_matched(reconciled_workspace):
    _, reconciliation, _ = reconciled_workspace
    ambiguous = [
        row for row in reconciliation["results"]
        if normalize_location(row.get("location_text_english")) in {
            "lane beside hotel priya opposite cbs",
            "chhatrapati shivaji vegetable market",
        }
    ]
    assert ambiguous
    assert all(row["match_status"] != "AUTO_MATCHED" for row in ambiguous)


def test_persistence_is_idempotent_preserves_review_and_operational_state(reconciled_workspace):
    database_path, reconciliation, before = reconciled_workspace
    first = persist_reconciliation(reconciliation, database_path)
    assert first["inserted"] == 7_259
    reviewed_vendor = next(row for row in reconciliation["results"] if row["candidate_zone_ids"])
    chosen_zone = reviewed_vendor["candidate_zone_ids"][0]
    reviewed = review_association(reviewed_vendor["vendor_id"], "CONFIRM", chosen_zone, "test_admin", "fixture review", database_path)
    assert reviewed["review_status"] == "CONFIRMED"
    rerun = reconcile_historical_associations(database_path)
    assert rerun["summary"]["preserved_reviewed"] == 1
    second = persist_reconciliation(rerun, database_path)
    assert second == {"inserted": 0, "updated": 0, "unchanged": 7_258, "preserved_reviewed": 1}
    associations = association_map(database_path)
    assert len(associations) == 7_259
    assert associations[reviewed_vendor["vendor_id"]]["matched_zone_id"] == chosen_zone
    assert associations[reviewed_vendor["vendor_id"]]["review_status"] == "CONFIRMED"
    summary = zone_association_summary(database_path)
    assert sum(zone["historical_vendor_count"] for zone in summary.values()) == 1_672
    assert all(sum(zone["historical_business_categories"].values()) == zone["historical_vendor_count"] for zone in summary.values())
    connection = connect(database_path)
    try:
        after = {
            "allocations": connection.execute("SELECT COUNT(*) AS total FROM allocations").fetchone()["total"],
            "slots": connection.execute("SELECT COUNT(*) AS total FROM pilot_slots").fetchone()["total"],
        }
        audit = connection.execute(
            "SELECT details_json FROM admin_audit_log WHERE entity_type = 'historical_vendor_zone_association'"
        ).fetchone()
    finally:
        connection.close()
    assert after == before
    assert json.loads(audit["details_json"])["after_zone_id"] == chosen_zone


def test_admin_historical_endpoints_require_authentication(monkeypatch, reconciled_workspace):
    database_path, _, _ = reconciled_workspace
    monkeypatch.setattr(context, "DATABASE_PATH", database_path)
    monkeypatch.setattr(context, "AUTH_TEST_BYPASS", False)
    with TestClient(app) as client:
        assert client.get("/api/admin/vendors?mapping_status=AUTO_MATCHED").status_code == 401
        assert client.get("/api/admin/zones/NE_F_001/historical-vendors").status_code == 401


def test_admin_zone_evidence_is_aggregate_safe_and_filterable(monkeypatch, reconciled_workspace):
    database_path, _, _ = reconciled_workspace
    monkeypatch.setattr(context, "DATABASE_PATH", database_path)
    monkeypatch.setattr(context, "AUTH_TEST_BYPASS", True)
    with TestClient(app) as client:
        zone_response = client.get("/api/admin/zones/PAN_R_005/historical-vendors")
        assert zone_response.status_code == 200
        body = zone_response.json()
        assert body["count"] > 0
        assert "not current occupancy" in body["notice"]
        assert all("phone" not in key for row in body["vendors"] for key in row)
        directory = client.get("/api/admin/vendors?zone_id=PAN_R_005&page_size=100")
        assert directory.status_code == 200
        assert directory.json()["total"] == body["count"]
        assert all(row["historical_association"]["matched_zone_id"] == "PAN_R_005" for row in directory.json()["vendors"])


def test_admin_vendor_directory_pages_are_complete_and_nonduplicated(monkeypatch, reconciled_workspace):
    database_path, _, _ = reconciled_workspace
    monkeypatch.setattr(context, "DATABASE_PATH", database_path)
    monkeypatch.setattr(context, "AUTH_TEST_BYPASS", True)
    with TestClient(app) as client:
        first = client.get("/api/admin/vendors?page=1&page_size=25")
        second = client.get("/api/admin/vendors?page=2&page_size=25")
        assert first.status_code == second.status_code == 200
        first_body, second_body = first.json(), second.json()
        assert first_body["total"] == second_body["total"]
        assert len(first_body["vendors"]) == len(second_body["vendors"]) == 25
        first_ids = {row["vendor_id"] for row in first_body["vendors"]}
        second_ids = {row["vendor_id"] for row in second_body["vendors"]}
        assert first_ids.isdisjoint(second_ids)
        assert first_body["accepted_zones"]
        assert all("phone" not in key for row in first_body["vendors"] for key in row)
