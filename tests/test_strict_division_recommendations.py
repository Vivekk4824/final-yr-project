import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch

import backend.api as api
from backend.database import connect, initialize_database
from backend.decision_policy import derive_mcda_weights
from backend.mcda_engine import DATA, recommend


class StrictDivisionRecommendationTests(unittest.TestCase):
    """Regression coverage using an isolated operational SQLite database."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "operational" / "test.db"
        initialize_database(self.database_path)
        self.database_patch = patch.object(api, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        self.auth_patch = patch.object(api, "AUTH_TEST_BYPASS", True)
        self.auth_patch.start()
        self.client = TestClient(api.app)
        candidates = pd.read_csv(
            DATA / "candidate_zone_snapshot.csv",
            dtype={"zone_id": str},
        )
        self.candidates = candidates.loc[
            candidates.zone_type.eq("FREE")
            & candidates.geometry_usable_for_reference_model.astype(str)
            .str.lower().isin(["true", "1", "yes"])
        ].copy()
        self.divisions = sorted(self.candidates.zone_division.dropna().unique())
        self.assertEqual(
            self.divisions,
            ["Nashik East", "Nashik Road", "Nashik West", "New Nashik", "Panchavati", "Satpur"],
        )
        self._close_all()

    def tearDown(self):
        self.client.close()
        self.auth_patch.stop()
        self.database_patch.stop()
        self.temporary.cleanup()

    def _close_all(self):
        with closing(connect(self.database_path)) as connection:
            connection.execute("UPDATE zone_live_status SET status = 'CLOSED'")
            connection.commit()

    def _open(self, zone_ids, capacity=5):
        with closing(connect(self.database_path)) as connection:
            for zone_id in zone_ids:
                connection.execute(
                    """UPDATE zone_live_status
                       SET official_capacity = ?, current_vendor_count = 0,
                           available_capacity = ?, status = 'OPEN'
                       WHERE zone_id = ?""",
                    (capacity, capacity, zone_id),
                )
            connection.commit()

    def _recommend(self, division="", **kwargs):
        return recommend(
            "food",
            division=division,
            top_n=kwargs.pop("top_n", 3),
            use_live_status=True,
            database_path=self.database_path,
            **kwargs,
        )

    def test_every_supported_division_is_a_strict_constraint(self):
        for division in self.divisions:
            with self.subTest(division=division):
                self._close_all()
                local_ids = self.candidates.loc[
                    self.candidates.zone_division.eq(division), "zone_id"
                ].head(3).tolist()
                outside_id = self.candidates.loc[
                    self.candidates.zone_division.ne(division), "zone_id"
                ].iloc[0]
                self._open(local_ids + [outside_id])
                result = self._recommend(division)
                self.assertEqual(len(result), 3)
                self.assertEqual(set(result.zone_division), {division})
                self.assertNotIn(outside_id, set(result.zone_id))
                self.assertFalse(result.fallback_used.any())

    def test_unknown_division_is_rejected_and_missing_preference_is_citywide(self):
        with self.assertRaisesRegex(ValueError, "Unknown division"):
            self._recommend("Not a canonical division")

        ids = self.candidates.groupby("zone_division").head(1).zone_id.tolist()
        self._open(ids)
        result = self._recommend("")
        self.assertEqual(len(result), 3)
        self.assertGreater(len(set(result.zone_division)), 1)
        self.assertFalse(result.attrs["strict_division_filter_applied"])

    def test_unavailable_and_unknown_capacity_zones_are_excluded(self):
        division = self.divisions[0]
        ids = self.candidates.loc[
            self.candidates.zone_division.eq(division), "zone_id"
        ].head(2).tolist()
        with closing(connect(self.database_path)) as connection:
            connection.execute(
                """UPDATE zone_live_status SET status = 'FULL',
                   official_capacity = 1, current_vendor_count = 1,
                   available_capacity = 0 WHERE zone_id = ?""",
                (ids[0],),
            )
            connection.execute(
                """UPDATE zone_live_status SET status = 'OPEN',
                   official_capacity = NULL, available_capacity = NULL
                   WHERE zone_id = ?""",
                (ids[1],),
            )
            connection.commit()
        self.assertTrue(self._recommend(division).empty)

    def test_fewer_than_three_are_returned_without_cross_division_fill(self):
        division = self.divisions[0]
        local_ids = self.candidates.loc[
            self.candidates.zone_division.eq(division), "zone_id"
        ].head(2).tolist()
        outside_id = self.candidates.loc[
            self.candidates.zone_division.ne(division), "zone_id"
        ].iloc[0]
        self._open(local_ids + [outside_id])
        result = self._recommend(division)
        self.assertEqual(set(result.zone_id), set(local_ids))
        self.assertEqual(len(result), 2)

    def test_priority_profiles_change_scores_only_within_selected_division(self):
        division = "Nashik Road"
        ids = self.candidates.loc[
            self.candidates.zone_division.eq(division), "zone_id"
        ].head(8).tolist()
        self._open(ids)
        balanced_weights = derive_mcda_weights({"priority_profile": "BALANCED"})["final_weights"]
        commercial_weights = derive_mcda_weights({"priority_profile": "COMMERCIAL"})["final_weights"]
        balanced = self._recommend(division, top_n=8, factor_weights=balanced_weights)
        commercial = self._recommend(division, top_n=8, factor_weights=commercial_weights)
        self.assertEqual(set(balanced.zone_division), {division})
        self.assertEqual(set(commercial.zone_division), {division})
        left = balanced.set_index("zone_id").score
        right = commercial.set_index("zone_id").score
        common = left.index.intersection(right.index)
        self.assertTrue(any(abs(left[zone] - right[zone]) > 1e-8 for zone in common))
        self.assertEqual(commercial.attrs["effective_factor_weights"]["preference"], 0)

    def test_api_empty_result_has_selected_division_notice(self):
        division = "Satpur"
        response = self.client.post(
            "/api/recommendations",
            json={"business": "food", "division": division, "top_n": 3},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["recommendations"], [])
        self.assertEqual(body["count"], 0)
        self.assertTrue(body["strict_division_filter_applied"])
        self.assertEqual(body["selected_division"], division)
        self.assertIn(division, body["notice"])
        self.assertEqual(body["effective_factor_weights"]["preference"], 0)


if __name__ == "__main__":
    unittest.main()
