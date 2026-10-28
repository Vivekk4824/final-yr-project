import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.business_aware_mcda import (
    CATEGORY_GIS_FEATURE_WEIGHTS,
    category_gis_scores,
)
from backend.database import connect, initialize_database
from backend.decision_policy import FACTOR_ORDER, derive_mcda_weights
from backend.mcda_engine import DATA, recommend, score_candidates
from backend.recommendation_explanations import explain


class BusinessAwareGISUnitTests(unittest.TestCase):
    def test_supported_categories_use_distinct_feature_mappings(self):
        expected = {"food", "clothing", "vegetable_fruit", "general_goods"}
        self.assertEqual(set(CATEGORY_GIS_FEATURE_WEIGHTS), expected)
        signatures = {
            tuple(sorted(mapping.items()))
            for mapping in CATEGORY_GIS_FEATURE_WEIGHTS.values()
        }
        self.assertEqual(len(signatures), len(expected))
        self.assertTrue(all(abs(sum(mapping.values()) - 1.0) < 1e-12 for mapping in CATEGORY_GIS_FEATURE_WEIGHTS.values()))
        self.assertTrue(all(
            "commercial_poi_count_250m" not in mapping
            for mapping in CATEGORY_GIS_FEATURE_WEIGHTS.values()
        ))

    def test_category_scores_are_business_specific(self):
        zones = pd.DataFrame({
            "food_poi_count_250m": [8, 0],
            "retail_poi_count_250m": [0, 8],
            "commercial_poi_count_250m": [1, 1],
            "market_poi_count_500m": [0, 0],
        })
        baseline = pd.Series([0.25, 0.25])
        food = category_gis_scores(zones, "food", baseline)["score"]
        clothing = category_gis_scores(zones, "clothing", baseline)["score"]
        self.assertGreater(food.iloc[0], food.iloc[1])
        self.assertGreater(clothing.iloc[1], clothing.iloc[0])

    def test_unknown_and_missing_feature_fallbacks_are_safe(self):
        baseline = pd.Series([0.2, 0.7])
        unknown = category_gis_scores(pd.DataFrame(index=[0, 1]), "unknown", baseline)
        pd.testing.assert_series_equal(unknown["score"], baseline)
        self.assertTrue(unknown["fallback"].all())

        missing = category_gis_scores(pd.DataFrame(index=[0, 1]), "food", baseline)
        pd.testing.assert_series_equal(missing["score"], baseline)
        self.assertTrue(missing["fallback"].all())


class BusinessAwareMCDAIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "operational" / "test.db"
        initialize_database(self.database_path)
        candidates = pd.read_csv(DATA / "candidate_zone_snapshot.csv", dtype={"zone_id": str})
        self.candidates = candidates.loc[
            candidates.zone_type.eq("FREE")
            & candidates.geometry_usable_for_reference_model.astype(str).str.lower().isin(["true", "1", "yes"])
        ].copy()
        with closing(connect(self.database_path)) as connection:
            connection.execute("UPDATE zone_live_status SET status = 'CLOSED'")
            connection.commit()

    def tearDown(self):
        self.temporary.cleanup()

    def _open(self, zone_ids, capacity=5):
        with closing(connect(self.database_path)) as connection:
            for zone_id in zone_ids:
                connection.execute(
                    """UPDATE zone_live_status
                       SET status = 'OPEN', official_capacity = ?,
                           current_vendor_count = 0, available_capacity = ?
                       WHERE zone_id = ?""",
                    (capacity, capacity, zone_id),
                )
            connection.commit()

    def _scored(self, business="food", division="Nashik East", experiment=False, weights=None, exclude_zone=""):
        return score_candidates(
            business,
            division=division,
            exclude_zone=exclude_zone,
            use_live_status=True,
            database_path=self.database_path,
            factor_weights=weights,
            business_aware_experiment=experiment,
        )

    def test_default_flag_is_disabled_and_baseline_is_identical(self):
        ids = self.candidates.loc[self.candidates.zone_division.eq("Nashik East"), "zone_id"].head(6).tolist()
        self._open(ids)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BUSINESS_AWARE_MCDA_EXPERIMENT", None)
            default = score_candidates("food", division="Nashik East", use_live_status=True, database_path=self.database_path)
        explicit = self._scored(experiment=False)
        pd.testing.assert_frame_equal(default, explicit)
        self.assertFalse(default.attrs["business_aware_mcda_experiment_enabled"])

    def test_experiment_replaces_only_commercial_factor(self):
        ids = self.candidates.loc[self.candidates.zone_division.eq("Nashik East"), "zone_id"].head(10).tolist()
        self._open(ids)
        baseline = self._scored(experiment=False).set_index("zone_id")
        experiment = self._scored(experiment=True).set_index("zone_id")
        common = baseline.index.intersection(experiment.index)
        for factor in ("business", "access", "facilities", "historical", "preference"):
            pd.testing.assert_series_equal(
                baseline.loc[common, f"{factor}_score"],
                experiment.loc[common, f"{factor}_score"],
            )
        self.assertEqual(tuple(FACTOR_ORDER), ("business", "commercial", "access", "facilities", "preference", "historical"))
        self.assertEqual(baseline.attrs["effective_factor_weights"], experiment.attrs["effective_factor_weights"])
        self.assertTrue(experiment.score.between(0, 100).all())
        explanation = explain(
            experiment.reset_index().iloc[0],
            experiment.attrs["effective_factor_weights"],
        )
        commercial = next(item for item in explanation if item["key"] == "commercial")
        self.assertEqual(commercial["label"], "Category-relevant GIS context")
        self.assertTrue(commercial["evidence"])
        self.assertIn("not verified demand", commercial["details"])

    def test_strict_division_full_zone_and_current_zone_exclusion(self):
        division = "Nashik Road"
        local = self.candidates.loc[self.candidates.zone_division.eq(division), "zone_id"].head(4).tolist()
        outside = self.candidates.loc[self.candidates.zone_division.ne(division), "zone_id"].iloc[0]
        self._open(local + [outside])
        with closing(connect(self.database_path)) as connection:
            connection.execute(
                """UPDATE zone_live_status
                   SET status='FULL', current_vendor_count=official_capacity,
                       available_capacity=0 WHERE zone_id=?""",
                (local[0],),
            )
            connection.execute(
                "UPDATE zone_live_status SET status='RESTRICTED' WHERE zone_id=?",
                (local[2],),
            )
            connection.commit()
        result = recommend(
            "clothing", division=division, top_n=10, exclude_zone=local[1],
            use_live_status=True, database_path=self.database_path,
            business_aware_experiment=True,
        )
        self.assertTrue(result.zone_division.eq(division).all())
        self.assertNotIn(local[0], set(result.zone_id))
        self.assertNotIn(local[1], set(result.zone_id))
        self.assertNotIn(local[2], set(result.zone_id))
        self.assertNotIn(outside, set(result.zone_id))

    def test_priority_weights_and_ranking_remain_deterministic(self):
        division = "Nashik West"
        ids = self.candidates.loc[self.candidates.zone_division.eq(division), "zone_id"].head(12).tolist()
        self._open(ids)
        balanced_weights = derive_mcda_weights({"priority_profile": "BALANCED"})["final_weights"]
        facilities_weights = derive_mcda_weights({"priority_profile": "FACILITIES"})["final_weights"]
        balanced = self._scored("general_goods", division, True, balanced_weights)
        repeated = self._scored("general_goods", division, True, balanced_weights)
        facilities = self._scored("general_goods", division, True, facilities_weights)
        self.assertEqual(balanced.zone_id.tolist(), repeated.zone_id.tolist())
        pd.testing.assert_series_equal(balanced.score, repeated.score)
        common = balanced.set_index("zone_id").index.intersection(facilities.set_index("zone_id").index)
        self.assertTrue(
            (balanced.set_index("zone_id").loc[common, "score"] - facilities.set_index("zone_id").loc[common, "score"]).abs().gt(1e-10).any()
        )

    def test_unknown_category_requires_explicit_experiment(self):
        with self.assertRaisesRegex(ValueError, "known business category"):
            score_candidates("unknown", business_aware_experiment=False)
        result = score_candidates("unknown", business_aware_experiment=True)
        self.assertTrue(result.category_gis_fallback_used.all())


if __name__ == "__main__":
    unittest.main()
