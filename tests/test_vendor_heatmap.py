import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.api as api
from backend.routers import vendors as vendor_routes
from backend.database import connect, initialize_database
from backend.services.pilot_slots import initialize_demo
from backend.services.vendor_heatmap import vendor_heatmap_data


class VendorHeatmapTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "heatmap.db"
        initialize_database(self.database_path)
        with closing(connect(self.database_path)) as connection:
            zone_ids = [row["zone_id"] for row in connection.execute(
                "SELECT zone_id FROM zone_live_status WHERE status = 'OPEN' ORDER BY zone_id LIMIT 2"
            )]
            zone_id = zone_ids[0]
            vendors = [
                ("V_FOOD_1", "food", "Panchavati", 20.0050, 73.7900),
                ("V_FOOD_2", "food", "Panchavati", 20.0055, 73.7905),
                ("V_CLOTH_1", "clothing", "Panchavati", 20.0050, 73.7900),
                ("V_MISSING", "general_goods", "Satpur", None, None),
                ("V_INVALID", "other", "Satpur", 95.0, 73.8),
            ]
            for vendor_id, category, locality, latitude, longitude in vendors:
                connection.execute(
                    """INSERT INTO operational_vendors
                       (vendor_id, vendor_type, business_category, preferred_division,
                        preferred_locality, preferred_latitude, preferred_longitude,
                        priority_profile, parking_preference, transport_preference,
                        market_preference, preferred_language, status, created_at, updated_at)
                       VALUES (?, 'NEW', ?, 'Nashik East', ?, ?, ?, 'BALANCED', 0, 0, 0,
                               'en', 'ACTIVE', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
                    (vendor_id, category, locality, latitude, longitude),
                )
            connection.execute(
                """INSERT INTO allocations
                   (allocation_id, vendor_id, zone_id, status, allocated_at, allocation_source,
                    created_at, updated_at)
                   VALUES ('ALLOC_HEAT', 'V_FOOD_1', ?, 'ACTIVE', '2026-01-01T00:00:00Z',
                           'ADMIN_APPROVED', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
                (zone_id,),
            )
            connection.commit()
        self.database_patch = patch.object(api, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        self.auth_patch = patch.object(api, "AUTH_TEST_BYPASS", True)
        self.auth_patch.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.auth_patch.stop()
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def test_service_uses_only_real_valid_database_coordinates(self):
        result = vendor_heatmap_data(database_path=self.database_path)
        self.assertEqual(result["summary"]["total_vendors"], 3)
        self.assertEqual(result["summary"]["unique_coordinates"], 2)
        self.assertEqual(result["data_quality"]["missing_coordinate_records"], 1)
        self.assertEqual(result["data_quality"]["invalid_coordinate_records"], 1)
        self.assertEqual(result["data_quality"]["duplicate_coordinate_groups"], 1)
        self.assertEqual(result["summary"]["category_distribution"], {"clothing": 1, "food": 2})
        self.assertEqual(result["mapping_summary"], {
            "total_records": 5,
            "mapped_records": 3,
            "unmapped_records": 2,
            "mapping_coverage_percent": 60.0,
        })
        self.assertEqual(
            {record["mapping_status"] for record in result["mapping_records"]},
            {"mapped", "unmapped"},
        )
        self.assertTrue(any(item["type"] == "zone" for item in result["filters"]["locations"]))
        self.assertTrue(any(item["type"] == "zone" and item["count"] == 0
                            for item in result["filters"]["locations"]))
        self.assertTrue(any(item["type"] == "locality" for item in result["filters"]["locations"]))
        self.assertNotIn("full_name", result["points"][0])
        self.assertNotIn("business_name", result["points"][0])

    def test_assigned_wgs84_slot_is_used_when_profile_pin_is_missing(self):
        initialize_demo(self.database_path, zone_id="PAN_F_019")
        with closing(connect(self.database_path)) as connection:
            slot = connection.execute(
                """SELECT zone_id, slot_id FROM pilot_slots
                   WHERE geometry_crs = 'EPSG:4326' AND is_deleted = 0
                   ORDER BY zone_id, slot_id LIMIT 1"""
            ).fetchone()
            self.assertIsNotNone(slot)
            connection.execute(
                """INSERT INTO allocations
                   (allocation_id, vendor_id, zone_id, status, allocated_at, allocation_source,
                    slot_id, created_at, updated_at)
                   VALUES ('ALLOC_SLOT_HEAT', 'V_MISSING', ?, 'ACTIVE', '2026-01-01T00:00:00Z',
                           'ADMIN_APPROVED', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
                (slot["zone_id"], slot["slot_id"]),
            )
            connection.execute(
                """UPDATE pilot_slots
                   SET status = 'OCCUPIED', assigned_vendor_id = 'V_MISSING',
                       active_allocation_id = 'ALLOC_SLOT_HEAT'
                   WHERE zone_id = ? AND slot_id = ?""",
                (slot["zone_id"], slot["slot_id"]),
            )
            connection.commit()

        result = vendor_heatmap_data(database_path=self.database_path)
        mapped = next(point for point in result["points"] if point["vendor_id"] == "V_MISSING")
        self.assertEqual(mapped["coordinate_source"], "assigned_slot")
        self.assertEqual(mapped["zone_id"], slot["zone_id"])
        self.assertEqual(result["data_quality"]["assigned_slot_coordinate_records"], 1)
        self.assertEqual(result["summary"]["total_vendors"], 4)
        status = next(record for record in result["mapping_records"] if record["vendor_id"] == "V_MISSING")
        self.assertEqual(status["mapping_status"], "mapped")
        self.assertEqual(status["coordinate_source"], "assigned_slot")

    def test_assigned_imported_vendor_without_operational_profile_is_mapped(self):
        initialize_demo(self.database_path, zone_id="PAN_F_019")
        with closing(connect(self.database_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT vendor_id FROM operational_vendors WHERE vendor_id = 'V2024_00001'"
            ).fetchone())
            slot = connection.execute(
                """SELECT zone_id, slot_id FROM pilot_slots
                   WHERE zone_id = 'PAN_F_019' AND geometry_crs = 'EPSG:4326'
                   ORDER BY slot_id LIMIT 1"""
            ).fetchone()
            connection.execute(
                """INSERT INTO allocations
                   (allocation_id, vendor_id, zone_id, status, allocated_at, allocation_source,
                    slot_id, created_at, updated_at)
                   VALUES ('ALLOC_IMPORTED_HEAT', 'V2024_00001', ?, 'ACTIVE',
                           '2026-01-01T00:00:00Z', 'LEGACY_IMPORT', ?,
                           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
                (slot["zone_id"], slot["slot_id"]),
            )
            connection.execute(
                """UPDATE pilot_slots
                   SET status = 'OCCUPIED', assigned_vendor_id = 'V2024_00001',
                       active_allocation_id = 'ALLOC_IMPORTED_HEAT'
                   WHERE zone_id = ? AND slot_id = ?""",
                (slot["zone_id"], slot["slot_id"]),
            )
            connection.commit()

        result = vendor_heatmap_data(database_path=self.database_path)
        point = next(point for point in result["points"] if point["vendor_id"] == "V2024_00001")
        self.assertEqual(point["coordinate_source"], "assigned_slot")
        self.assertNotEqual(point["business_category"], "unknown")
        self.assertEqual(result["data_quality"]["active_operational_records"], 5)
        self.assertEqual(result["data_quality"]["assigned_slot_records"], 1)
        self.assertEqual(result["data_quality"]["assigned_slot_only_records"], 1)
        self.assertEqual(result["mapping_summary"]["mapped_records"], 4)

    def test_category_and_location_filters_are_exact_and_empty_safe(self):
        unfiltered = vendor_heatmap_data(database_path=self.database_path)
        locality = next(item["value"] for item in unfiltered["filters"]["locations"]
                        if item["type"] == "locality")
        food = vendor_heatmap_data(business_category="food", database_path=self.database_path)
        self.assertEqual(food["summary"]["total_vendors"], 2)
        self.assertEqual(food["mapping_summary"]["total_records"], 2)
        self.assertTrue(all(point["business_category"] == "food" for point in food["points"]))
        local = vendor_heatmap_data(location_key=locality, database_path=self.database_path)
        self.assertGreater(local["summary"]["total_vendors"], 0)
        scoped_competition = vendor_heatmap_data(
            business_category="food", location_key=locality, database_path=self.database_path
        )
        self.assertEqual(len(scoped_competition["competition_points"]), 2)
        empty = vendor_heatmap_data(business_category="not-a-real-category", database_path=self.database_path)
        self.assertEqual(empty["points"], [])
        self.assertIsNone(empty["summary"]["vendor_density_per_km2"])

    def test_admin_endpoint_exposes_heatmap_contract(self):
        response = self.client.get("/api/admin/vendor-heatmap?business_category=food")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["summary"]["total_vendors"], 2)
        self.assertEqual(body["selected_filters"]["business_category"], "food")
        self.assertIn("does not establish", body["density_notice"])

    def test_vendor_insights_are_category_filtered_and_aggregate_only(self):
        with closing(connect(self.database_path)) as connection:
            zone_ids = [row["zone_id"] for row in connection.execute(
                "SELECT zone_id FROM zone_live_status WHERE status = 'OPEN' ORDER BY zone_id LIMIT 2"
            )]
            connection.execute(
                """INSERT INTO operational_vendors
                   (vendor_id, vendor_type, business_category, preferred_division,
                    preferred_locality, preferred_latitude, preferred_longitude,
                    priority_profile, parking_preference, transport_preference,
                    market_preference, preferred_language, status, created_at, updated_at)
                   VALUES ('V_FOOD_3', 'NEW', 'food', 'Nashik East', 'Panchavati',
                           20.0051, 73.7901, 'BALANCED', 0, 0, 0, 'en', 'ACTIVE',
                           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
            )
            connection.execute(
                """INSERT INTO operational_vendors
                   (vendor_id, vendor_type, business_category, preferred_division,
                    preferred_locality, preferred_latitude, preferred_longitude,
                    priority_profile, parking_preference, transport_preference,
                    market_preference, preferred_language, status, created_at, updated_at)
                   VALUES ('V_FOOD_4', 'NEW', 'food', 'Nashik East', 'Panchavati',
                           20.0052, 73.7902, 'BALANCED', 0, 0, 0, 'en', 'ACTIVE',
                           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
            )
            connection.commit()

        zone_locations = {
            zone_ids[0]: {"coordinates": [73.7900, 20.0050], "location_source": "TEST_REFERENCE"},
            zone_ids[1]: {"coordinates": [75.0000, 20.5000], "location_source": "TEST_REFERENCE"},
        }
        with patch("backend.services.vendor_location_insights.resolve_zone_locations", return_value=zone_locations):
            with patch.object(vendor_routes, "request_session", return_value={"role": "VENDOR", "vendor_id": "V_FOOD_1"}):
                response = self.client.get(
                    f"/api/vendors/me/location-insights?zone_id={zone_ids[0]}&zone_id={zone_ids[1]}"
                    "&business_category=clothing"
                )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["business_category"], "food")
        self.assertEqual(body["coverage"], {
            "total_records": 4, "mapped_records": 4, "unmapped_records": 0, "status": "COMPLETE",
        })
        self.assertEqual(body["recommended_zones"][0]["nearby_same_category"], {
            "100m": 3, "250m": 3, "500m": 3,
        })
        self.assertEqual(body["recommended_zones"][1]["nearby_same_category"], {
            "100m": 0, "250m": 0, "500m": 0,
        })
        self.assertEqual(body["recommended_zones"][1]["counts_status"], "AVAILABLE")
        self.assertTrue(all(cell["count"] >= 3 for cell in body["heatmap"]["cells"]))
        self.assertTrue(all(set(cell) == {"latitude", "longitude", "count"} for cell in body["heatmap"]["cells"]))
        self.assertNotIn("V_FOOD_1", response.text)
        self.assertNotIn("V_FOOD_2", response.text)
        self.assertNotIn("vendor_id", body)
        self.assertNotIn("business_name", response.text)

    def test_vendor_insights_mark_missing_coordinates_unavailable_not_zero(self):
        with patch.object(vendor_routes, "request_session", return_value={"role": "VENDOR", "vendor_id": "V_MISSING"}):
            response = self.client.get("/api/vendors/me/location-insights")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["coverage"]["status"], "NO_MAPPED_COORDINATES")
        self.assertEqual(body["heatmap"]["status"], "NO_MAPPED_COORDINATES")
        self.assertEqual(body["heatmap"]["cells"], [])


if __name__ == "__main__":
    unittest.main()
