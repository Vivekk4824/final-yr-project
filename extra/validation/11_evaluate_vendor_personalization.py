"""Compare ranking policies on the bundled GIS and a read-only SQLite snapshot."""
from __future__ import annotations

import json
from collections import Counter
from contextlib import closing
from itertools import combinations
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.recommendation.business_aware_mcda import CATEGORY_GIS_FEATURE_WEIGHTS, FEATURE_SCALES
from backend.core.data_paths import dataset_path
from backend.recommendation.decision_policy import derive_mcda_weights
from backend.recommendation.location_ranking import DISTANCE_RADII_KM, LocationRankingPolicy, apply_location_ranking, reviewed_coordinates
from backend.recommendation.mcda_engine import CATEGORIES, rank_candidates, score_candidates
from backend.repositories.database import get_live_zone_status_map
from backend.services.eligibility import zone_ineligibility_reason

PROFILES = [
    {"priority_profile": "COMMERCIAL", "market_preference": True},
    {"priority_profile": "ACCESSIBILITY", "transport_preference": True},
    {"priority_profile": "FACILITIES", "parking_preference": True},
]
COMPARISON_WEIGHTS = (0.10, 0.15, 0.20)


def pair_metrics(scenarios, hold_fixed):
    pairs = [(a, b) for a, b in combinations(scenarios, 2) if all(a[k] == b[k] for k in hold_fixed)]
    return {
        "pairs": len(pairs),
        **{
            policy: {
                "different_top_1": sum(a[policy][0] != b[policy][0] for a, b in pairs),
                "mean_top_3_overlap": sum(len(set(a[policy]) & set(b[policy])) / 3 for a, b in pairs) / len(pairs),
            }
            for policy in ("baseline", "business_only", "combined")
        },
    }


def evaluate(database):
    live = get_live_zone_status_map(database)
    official = pd.read_csv(dataset_path("official_zones"))
    eligible = {
        row.zone_id for row in official.itertuples()
        if zone_ineligibility_reason(row.zone_type, live.get(row.zone_id)) is None
    }
    candidates = score_candidates("food", use_live_status=True, database_path=database, include_unscorable=True,
                                 business_aware_experiment=False)
    assert set(candidates.zone_id) == eligible
    coordinates = reviewed_coordinates(candidates)
    anchors = candidates[["zone_id", "zone_division"]].join(coordinates).dropna().sort_values("longitude")
    scenario_results = []
    radius_shortfalls = Counter()
    policy = LocationRankingPolicy(proximity_weight=0.25)
    for index, (division, pins) in enumerate(anchors.groupby("zone_division", sort=True)):
        expected = set(candidates.loc[candidates.zone_division.eq(division), "zone_id"])
        for business in CATEGORIES:
            for profile in ({"priority_profile": "BALANCED"}, PROFILES[index % len(PROFILES)]):
                settings = dict(business=business, division=division, use_live_status=True, database_path=database,
                                include_unscorable=True, factor_weights=derive_mcda_weights(profile)["final_weights"])
                baseline = score_candidates(**settings, business_aware_experiment=False)
                business_aware = score_candidates(**settings, business_aware_experiment=True)
                assert set(baseline.zone_id) == set(business_aware.zone_id) == expected
                base_top = rank_candidates(baseline)
                business_top = rank_candidates(business_aware)
                for pin in (pins.iloc[0], pins.iloc[-1]):
                    location = (pin.latitude, pin.longitude)
                    distance_only = apply_location_ranking(baseline, location, policy)
                    combined = apply_location_ranking(business_aware, location, policy)
                    distance_top = rank_candidates(distance_only)
                    combined_top = rank_candidates(combined)
                    alternatives = {
                        str(weight): rank_candidates(apply_location_ranking(
                            business_aware, location, LocationRankingPolicy(proximity_weight=weight)
                        ))
                        for weight in COMPARISON_WEIGHTS
                    }
                    assert set(combined.zone_id) == expected
                    assert not combined.loc[combined.score.isna(), "personalized_score"].notna().any()
                    assert not combined.loc[combined.distance_km.isna(), "personalized_score"].notna().any()
                    for radius in DISTANCE_RADII_KM:
                        nearby = rank_candidates(combined.loc[combined.distance_km.le(radius)])
                        assert nearby.distance_km.le(radius).all()
                        radius_shortfalls[radius] += int(len(nearby) < 3)
                    for results in (base_top, business_top, distance_top, combined_top):
                        assert len(results) == 3
                        assert all(zone in eligible and live[zone]["available_capacity"] > 0 for zone in results.zone_id)
                        assert results.zone_division.eq(division).all()
                    lookup = combined.set_index("zone_id")
                    record = {
                        "division": division, "business": business, "profile": profile["priority_profile"], "pin": pin.zone_id,
                        "baseline": base_top.zone_id.tolist(), "business_only": business_top.zone_id.tolist(),
                        "location_only": distance_top.zone_id.tolist(), "combined": combined_top.zone_id.tolist(),
                        "top_1_original_loss": base_top.score.iloc[0] - combined_top.original_mcda_score.iloc[0],
                        "mean_original_loss": base_top.score.mean() - combined_top.original_mcda_score.mean(),
                        "business_only_original_loss": base_top.score.mean() - business_top.original_mcda_score.mean(),
                        "distance_improvement_km": lookup.loc[base_top.zone_id, "distance_km"].mean() - combined_top.distance_km.mean(),
                    }
                    for weight, alternative in alternatives.items():
                        record[weight] = alternative.zone_id.tolist()
                        record[f"loss_{weight}"] = base_top.score.mean() - alternative.original_mcda_score.mean()
                        record[f"distance_gain_{weight}"] = lookup.loc[base_top.zone_id, "distance_km"].mean() - alternative.distance_km.mean()
                    if business in CATEGORY_GIS_FEATURE_WEIGHTS:
                        relevance = lookup.category_gis_compatibility_score
                        record["business_only_gis_gain"] = relevance.loc[business_top.zone_id].mean() - relevance.loc[base_top.zone_id].mean()
                        record["combined_gis_gain"] = relevance.loc[combined_top.zone_id].mean() - relevance.loc[distance_top.zone_id].mean()
                    scenario_results.append(record)

    totals = pd.DataFrame(scenario_results)
    comparison = {
        name: {
            "top_1_changed": sum(a[0] != b[0] for a, b in zip(totals.baseline, totals[name])),
            "top_3_changed": sum(set(a) != set(b) for a, b in zip(totals.baseline, totals[name])),
            "mean_top_3_overlap": sum(len(set(a) & set(b)) / 3 for a, b in zip(totals.baseline, totals[name])) / len(totals),
        }
        for name in ("business_only", "location_only", "combined", *(str(weight) for weight in COMPARISON_WEIGHTS))
    }
    return {
        "scenarios": len(totals),
        "eligible_zones": len(eligible),
        "unscorable_zones": int(candidates.score.isna().sum()),
        "no_reviewed_coordinates": int(coordinates.latitude.isna().sum()),
        "poi_missing": {key: int(candidates[key].isna().sum()) for key in FEATURE_SCALES},
        "poi_positive": {key: int(candidates[key].gt(0).sum()) for key in FEATURE_SCALES},
        "comparison": comparison,
        "pairwise_location": pair_metrics(scenario_results, ["division", "business", "profile"]),
        "pairwise_business": pair_metrics(scenario_results, ["division", "pin", "profile"]),
        "pairwise_priority_and_facilities": pair_metrics(scenario_results, ["division", "pin", "business"]),
        "original_loss": totals[["top_1_original_loss", "mean_original_loss", "business_only_original_loss"]].describe(percentiles=[.5, .9]).to_dict(),
        "mean_distance_improvement_km": totals.distance_improvement_km.mean(),
        "mean_category_gis_gain": totals[["business_only_gis_gain", "combined_gis_gain"]].mean().to_dict(),
        "shortfalls_by_radius_km": dict(radius_shortfalls),
        "alternative_proximity_weights": {
            str(weight): {
                "mean_original_loss": totals[f"loss_{weight}"].mean(),
                "p90_original_loss": totals[f"loss_{weight}"].quantile(.9),
                "mean_distance_improvement_km": totals[f"distance_gain_{weight}"].mean(),
            }
            for weight in COMPARISON_WEIGHTS
        },
        "examples": scenario_results,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="vendormap-ranking-") as directory:
        copy = Path(directory) / "snapshot.db"
        source = dataset_path("database").resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source, uri=True)) as existing, closing(sqlite3.connect(copy)) as snapshot:
            existing.backup(snapshot)
        print(json.dumps(evaluate(copy), indent=2, allow_nan=False))
