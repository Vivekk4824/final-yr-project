import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend import database as db
from backend.geo import pilot_geometry as gis
from backend.services import pilot_slots


class InteractiveSlotAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "slots.db"
        db.initialize_database(self.path)
        self.layout = pilot_slots.initialize_demo(self.path, "PAN_F_031")

    def tearDown(self):
        self.temp.cleanup()

    def geometry(self, longitude=73.79481222, latitude=20.00988107):
        return gis.pose_geometry(longitude, latitude, 0, width_m=2, depth_m=2)

    def create_slot(self, longitude=73.79481222, latitude=20.00988107):
        return pilot_slots.create_drawn_slot(
            self.geometry(longitude, latitude), actor="test-admin", review_confirmed=True,
            width_m=2, depth_m=2, database_path=self.path, zone_id="PAN_F_031",
        )

    def test_empty_initialization_does_not_invent_positions(self):
        self.assertEqual(self.layout["slots"], [])
        self.assertEqual(self.layout["summary"]["listed_capacity"], 30)
        self.assertEqual(self.layout["summary"]["remaining_uncreated_capacity"], 30)
        self.assertEqual(self.layout["geometry_verification_status"], "PROVISIONAL_NOT_SURVEYED")

    def test_any_official_zone_opens_an_empty_provisional_map(self):
        layout = pilot_slots.initialize_demo(self.path, "NE_F_001")
        self.assertEqual(layout["zone_id"], "NE_F_001")
        self.assertEqual(layout["slots"], [])
        self.assertFalse(layout["operational_enabled"])
        self.assertIn("longitude", layout["reference_point"])
        self.assertIn("latitude", layout["reference_point"])
        slot = pilot_slots.create_drawn_slot(
            self.geometry(), actor="test-admin", review_confirmed=True,
            width_m=2, depth_m=2, database_path=self.path, zone_id="NE_F_001",
        )
        pilot_slots.delete_drawn_slot(
            slot["slot_id"], actor="test-admin", expected_updated_at=slot["updated_at"],
            database_path=self.path, zone_id="NE_F_001",
        )
        self.assertEqual(pilot_slots.get_layout(self.path, "NE_F_001")["slots"], [])

    def test_drawing_is_rejected_for_no_vending_zones(self):
        with self.assertRaises(db.OperationalValidationError):
            pilot_slots.create_drawn_slot(
                self.geometry(), actor="test-admin", review_confirmed=True,
                width_m=2, depth_m=2, database_path=self.path, zone_id="NV_001",
            )

    def test_metric_rectangle_overlap_and_safe_delete(self):
        slot = self.create_slot()
        self.assertEqual(slot["slot_id"], "S001")
        self.assertAlmostEqual(slot["width_m"], 2, delta=.05)
        self.assertAlmostEqual(slot["depth_m"], 2, delta=.05)
        with self.assertRaises(db.OperationalConflictError):
            self.create_slot()
        pilot_slots.delete_drawn_slot("S001", actor="test-admin",
            expected_updated_at=slot["updated_at"], database_path=self.path, zone_id="PAN_F_031")
        self.assertEqual(pilot_slots.get_layout(self.path, "PAN_F_031")["slots"], [])

    def test_new_slots_reuse_the_lowest_soft_deleted_id(self):
        deleted = self.create_slot()
        pilot_slots.delete_drawn_slot(
            deleted["slot_id"], actor="test-admin", expected_updated_at=deleted["updated_at"],
            database_path=self.path, zone_id="PAN_F_031",
        )
        created = self.create_slot(longitude=73.79484)
        self.assertEqual(created["slot_id"], "S001")

    def test_slot_ids_and_active_slots_cannot_exceed_official_capacity(self):
        created = [
            self.create_slot(longitude=73.79481222 + index * 0.00005)
            for index in range(30)
        ]

        self.assertEqual([slot["slot_id"] for slot in created],
                         [f"S{index:03d}" for index in range(1, 31)])
        with self.assertRaises(db.OperationalConflictError):
            self.create_slot(longitude=73.79481222 + 30 * 0.00005)

    def test_request_reserves_cancel_releases_and_approval_assigns_atomically(self):
        first = self.create_slot()
        second = self.create_slot(longitude=73.79484)
        request = db.create_allocation_request(
            "V2024_00001", "PAN_F_031", "NEW_ALLOCATION", slot_id=first["slot_id"],
            database_path=self.path,
        )
        reserved = pilot_slots.get_layout(self.path, "PAN_F_031")["slots"][0]
        self.assertEqual(reserved["status"], "RESERVED")
        with self.assertRaises(db.OperationalConflictError):
            db.create_allocation_request("V2024_00002", "PAN_F_031", "NEW_ALLOCATION",
                                         slot_id=first["slot_id"], database_path=self.path)
        db.cancel_allocation_request(request["request_id"], self.path)
        self.assertEqual(pilot_slots.get_layout(self.path, "PAN_F_031")["slots"][0]["status"], "AVAILABLE")

        request = db.create_allocation_request(
            "V2024_00001", "PAN_F_031", "NEW_ALLOCATION", slot_id=second["slot_id"],
            database_path=self.path,
        )
        result = db.approve_allocation_request(request["request_id"], "test-admin", database_path=self.path)
        assigned = next(item for item in pilot_slots.get_layout(self.path, "PAN_F_031")["slots"] if item["slot_id"] == second["slot_id"])
        self.assertEqual(assigned["status"], "OCCUPIED")
        self.assertEqual(assigned["assigned_vendor_id"], "V2024_00001")
        self.assertEqual(result["allocation"]["slot_id"], second["slot_id"])

    def test_mapping_existing_legacy_allocation_does_not_increment_occupancy(self):
        slot = self.create_slot()
        now = db.utc_now()
        with db.transaction(self.path, immediate=True) as connection:
            connection.execute("""INSERT INTO allocations(allocation_id,vendor_id,zone_id,status,allocated_at,
                allocation_source,created_at,updated_at) VALUES(?, ?, ?, 'ACTIVE', ?, 'LEGACY_IMPORT', ?, ?)""",
                ("ALLOC_LEGACY_SLOT", "V2024_00003", "PAN_F_031", now, now, now))
            before = connection.execute("SELECT current_vendor_count FROM zone_live_status WHERE zone_id='PAN_F_031'").fetchone()[0]
        pilot_slots.update_slot(slot["slot_id"], "OCCUPIED", "V2024_00003", actor="test-admin",
            expected_updated_at=slot["updated_at"], database_path=self.path, zone_id="PAN_F_031")
        with closing(db.connect(self.path)) as connection:
            after = connection.execute("SELECT current_vendor_count FROM zone_live_status WHERE zone_id='PAN_F_031'").fetchone()[0]
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
