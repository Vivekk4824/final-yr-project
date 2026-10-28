from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.repositories.database import (
    OFFICIAL_ZONES_PATH,
    _official_zone_type_map,
    connect,
    initialize_database,
    transaction,
    utc_now,
    get_live_zone_status_map,
    create_allocation_request,
    OperationalConflictError,
)
from backend.services.legacy_allocation_import import (
    active_vendor_category_counts,
    apply_legacy_import,
    build_legacy_import_plan,
)
from backend.services.capacity_analysis import zone_capacity_analysis
from backend.services.historical_occupancy_reconciliation import audit_historical_occupancy


class LegacyAllocationImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "operational.db"
        initialize_database(self.database)
        db = connect(self.database)
        try:
            types = _official_zone_type_map(str(Path(OFFICIAL_ZONES_PATH).resolve()))
            self.unknown_zone = next(
                row["zone_id"]
                for row in db.execute(
                    "SELECT zone_id FROM zone_live_status WHERE official_capacity IS NULL"
                )
                if types.get(row["zone_id"]) == "FREE"
            )
        finally:
            db.close()
        now = utc_now()
        with transaction(self.database, immediate=True) as db:
            db.execute(
                "UPDATE zone_live_status SET official_capacity = 1, current_vendor_count = 0, "
                "available_capacity = 1, status = 'CLOSED' WHERE zone_id = 'NE_F_010'"
            )
            for vendor_id, zone_id, category, match_status in (
                ("V2024_00001", "NE_F_010", "vegetable_fruit", "AUTO_MATCHED"),
                ("V2024_00002", "NE_F_010", "flower", "AUTO_MATCHED"),
                ("V2024_00003", self.unknown_zone, "clothing", "AUTO_MATCHED"),
                ("V2024_00004", "NE_F_010", "food", "REVIEW_REQUIRED"),
            ):
                db.execute(
                    "INSERT INTO historical_vendor_zone_associations "
                    "(vendor_id, matched_zone_id, candidate_zone_ids_json, business_category, "
                    "match_status, evidence_types_json, source_provenance, algorithm_version, "
                    "review_status, created_at, updated_at) VALUES (?, ?, '[]', ?, ?, '[]', "
                    "'fixture', 'test', 'UNREVIEWED', ?, ?)",
                    (vendor_id, zone_id, category, match_status, now, now),
                )

    def tearDown(self):
        self.temporary.cleanup()

    def test_dry_run_is_read_only_and_reports_exclusions(self):
        before = connect(self.database)
        try:
            allocation_count = before.execute(
                "SELECT COUNT(*) AS count FROM allocations"
            ).fetchone()["count"]
            live_before = [dict(row) for row in before.execute(
                "SELECT * FROM zone_live_status ORDER BY zone_id"
            )]
        finally:
            before.close()

        report = build_legacy_import_plan(self.database)

        after = connect(self.database)
        try:
            self.assertEqual(
                after.execute("SELECT COUNT(*) AS count FROM allocations").fetchone()["count"],
                allocation_count,
            )
            self.assertEqual(
                [dict(row) for row in after.execute("SELECT * FROM zone_live_status ORDER BY zone_id")],
                live_before,
            )
        finally:
            after.close()
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["skipped_counts"]["needs_review"], 1)
        self.assertGreater(report["skipped_counts"]["missing_mapping"], 0)
        self.assertEqual(len(report["capacity_overflow_zones"]), 1)
        self.assertEqual(len(report["unknown_capacity_zones"]), 1)

    def test_apply_is_idempotent_rebuilds_capacity_and_preserves_status(self):
        first = apply_legacy_import(self.database)
        self.assertEqual(first["imported_count"], 3)
        db = connect(self.database)
        try:
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM allocations ORDER BY vendor_id"
            )]
            overflow = db.execute(
                "SELECT * FROM zone_live_status WHERE zone_id = 'NE_F_010'"
            ).fetchone()
            unknown = db.execute(
                "SELECT * FROM zone_live_status WHERE zone_id = ?", (self.unknown_zone,)
            ).fetchone()
        finally:
            db.close()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["allocation_source"] == "LEGACY_IMPORT" for row in rows))
        self.assertTrue(all(row["approved_by"] is None for row in rows))
        self.assertEqual(overflow["current_vendor_count"], 2)
        self.assertEqual(overflow["available_capacity"], 0)
        self.assertEqual(overflow["status"], "CLOSED")
        self.assertEqual(unknown["current_vendor_count"], 1)
        self.assertIsNone(unknown["available_capacity"])
        capacity = zone_capacity_analysis(self.database)["NE_F_010"]
        self.assertEqual(capacity["operational_occupancy"], 2)
        self.assertEqual(capacity["operational_available"], 0)
        self.assertEqual(capacity["historical_planning_count"], 0)
        self.assertEqual(capacity["planning_load"], 2)
        self.assertEqual(capacity["planning_available"], 0)

        second = apply_legacy_import(self.database)
        self.assertEqual(second["imported_count"], 0)
        self.assertEqual(second["candidate_count"], 0)

    def test_category_counts_resolve_historical_profiles(self):
        apply_legacy_import(self.database)
        counts = active_vendor_category_counts("vegetable_fruit", self.database)
        self.assertEqual(counts["NE_F_010"]["current_total_vendors"], 2)
        self.assertEqual(counts["NE_F_010"]["current_same_category_vendors"], 1)

    def test_released_vendor_is_never_resurrected(self):
        now = utc_now()
        with transaction(self.database, immediate=True) as db:
            db.execute(
                "INSERT INTO historical_vendor_zone_associations "
                "(vendor_id, matched_zone_id, candidate_zone_ids_json, business_category, "
                "match_status, evidence_types_json, source_provenance, algorithm_version, "
                "review_status, created_at, updated_at) VALUES "
                "('V2024_00005', 'NE_F_010', '[]', 'food', 'AUTO_MATCHED', '[]', "
                "'fixture', 'test', 'UNREVIEWED', ?, ?)",
                (now, now),
            )
            db.execute(
                "INSERT INTO allocations (allocation_id, vendor_id, zone_id, request_id, "
                "status, allocated_at, released_at, approved_by, allocation_source, created_at, updated_at) "
                "VALUES ('RELEASED_FIXTURE', 'V2024_00005', 'NE_F_010', NULL, 'RELEASED', "
                "?, ?, 'admin', 'ADMIN_APPROVED', ?, ?)",
                (now, now, now, now),
            )
        plan = build_legacy_import_plan(self.database)
        self.assertEqual(plan["skipped_counts"]["released_history"], 1)
        self.assertEqual(plan["candidate_count"], 3)

    def test_active_allocation_in_different_zone_wins(self):
        now = utc_now()
        with transaction(self.database, immediate=True) as db:
            db.execute(
                "INSERT INTO historical_vendor_zone_associations "
                "(vendor_id, matched_zone_id, candidate_zone_ids_json, business_category, "
                "match_status, evidence_types_json, source_provenance, algorithm_version, "
                "review_status, created_at, updated_at) VALUES "
                "('V2024_00006', 'NE_F_010', '[]', 'food', 'AUTO_MATCHED', '[]', "
                "'fixture', 'test', 'UNREVIEWED', ?, ?)",
                (now, now),
            )
            db.execute(
                "INSERT INTO allocations (allocation_id, vendor_id, zone_id, request_id, "
                "status, allocated_at, released_at, approved_by, allocation_source, created_at, updated_at) "
                "VALUES ('RELOCATED_FIXTURE', 'V2024_00006', ?, NULL, 'ACTIVE', ?, NULL, "
                "'admin', 'ADMIN_APPROVED', ?, ?)",
                (self.unknown_zone, now, now, now),
            )
        plan = build_legacy_import_plan(self.database)
        self.assertEqual(plan["existing_active_allocation_wins"], 1)
        self.assertEqual(plan["candidate_count"], 3)

    def test_derived_zone_counts_override_stale_counters_consistently(self):
        apply_legacy_import(self.database)
        with transaction(self.database, immediate=True) as db:
            db.execute(
                "UPDATE zone_live_status SET current_vendor_count=0, available_capacity=1 "
                "WHERE zone_id='NE_F_010'"
            )
        live = get_live_zone_status_map(self.database)["NE_F_010"]
        capacity = zone_capacity_analysis(self.database)["NE_F_010"]
        self.assertEqual(live["current_vendor_count"], 2)
        self.assertEqual(live["available_capacity"], 0)
        self.assertEqual(capacity["operational_occupancy"], 2)
        self.assertEqual(capacity["operational_available"], 0)

    def test_request_capacity_check_uses_active_allocations_not_stale_counter(self):
        apply_legacy_import(self.database)
        with transaction(self.database, immediate=True) as db:
            db.execute(
                "UPDATE zone_live_status SET current_vendor_count=0, available_capacity=1, "
                "status='OPEN' WHERE zone_id='NE_F_010'"
            )
        with self.assertRaisesRegex(OperationalConflictError, "ineligible|no available capacity"):
            create_allocation_request(
                "NV_CAPACITY_TEST", "NE_F_010", "NEW_ALLOCATION",
                database_path=self.database,
            )

    def test_read_only_audit_classifies_missing_and_does_not_write(self):
        before = connect(self.database)
        try:
            allocation_count = before.execute("SELECT COUNT(*) total FROM allocations").fetchone()["total"]
        finally:
            before.close()
        report = audit_historical_occupancy(self.database, zone_id="NE_F_010")
        self.assertEqual(report["mode"], "READ_ONLY_DRY_RUN")
        self.assertGreaterEqual(report["eligible_missing_count"], 2)
        after = connect(self.database)
        try:
            self.assertEqual(after.execute("SELECT COUNT(*) total FROM allocations").fetchone()["total"], allocation_count)
        finally:
            after.close()


if __name__ == "__main__":
    unittest.main()

