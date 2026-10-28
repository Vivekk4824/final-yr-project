"""Read-only 96-scenario evaluation of the business-aware MCDA experiment.

The script writes only to ``reports/business_aware_mcda``. It reads the live
operational snapshot once, freezes that snapshot in memory, and never invokes
database mutation functions.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend.mcda_engine as mcda
from backend.business_aware_mcda import (
    CATEGORY_GIS_FEATURE_WEIGHTS,
    FALLBACK_CATEGORIES,
    FEATURE_LABELS,
    FEATURE_SCALES,
    POLICY_VERSION,
)
from backend.core.data_paths import CATALOG, dataset_path
from backend.decision_policy import derive_mcda_weights
from backend.repositories.database import DATABASE_PATH


OUT = ROOT / "reports" / "business_aware_mcda"
DIVISIONS = ["Nashik East", "Nashik West", "Nashik Road", "New Nashik", "Panchavati", "Satpur"]
BUSINESSES = ["food", "clothing", "vegetable_fruit", "general_goods"]
PROFILES = ["BALANCED", "COMMERCIAL", "ACCESSIBILITY", "FACILITIES"]
AUDIT_FEATURES = [
    "food_poi_count_250m",
    "market_poi_count_500m",
    "retail_poi_count_250m",
    "service_poi_count_250m",
    "commercial_poi_count_250m",
    "pedestrian_road_density_250m_per_km2",
    "distance_to_major_road_m",
    "distance_to_bus_access_m",
    "healthcare_count_500m",
    "education_count_500m",
    "toilet_count_500m",
    "parking_count_500m",
]


def _ids(frame: pd.DataFrame, limit: int) -> list[str]:
    return frame.loc[frame.score.notna(), "zone_id"].head(limit).astype(str).tolist()


def _mean(values) -> float | None:
    numeric = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    return float(numeric.mean()) if len(numeric) else None


def _pairwise_top3_overlap(groups: list[set[str]]) -> float:
    pairs = list(combinations(groups, 2))
    if not pairs:
        return 1.0
    return float(np.mean([len(left & right) / 3.0 for left, right in pairs]))


def feature_availability(candidate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in AUDIT_FEATURES:
        exists = feature in candidate.columns
        values = pd.to_numeric(candidate[feature], errors="coerce") if exists else pd.Series(dtype=float)
        present = int(values.notna().sum()) if exists else 0
        rows.append({
            "feature": feature,
            "available_in_active_snapshot": exists,
            "candidate_rows": len(candidate),
            "non_missing_rows": present,
            "missing_rows": len(candidate) - present,
            "nonzero_rows": int(values.fillna(0).gt(0).sum()) if exists else 0,
            "zero_rows_among_non_missing": int(values.eq(0).sum()) if exists else 0,
            "median": float(values.median()) if present else None,
            "maximum": float(values.max()) if present else None,
            "used_by_experiment": feature in FEATURE_SCALES,
            "factor_role": (
                "CATEGORY_GIS_COMMERCIAL_REPLACEMENT"
                if feature in FEATURE_SCALES
                else "EXISTING_ACCESS_OR_FACILITIES_FACTOR"
            ),
        })
    return pd.DataFrame(rows)


def mapping_report() -> pd.DataFrame:
    rationale = {
        "food": "Mapped food POIs are the strongest category-specific context; market and service subtypes provide secondary surroundings context.",
        "clothing": "Mapped retail activity is the closest available clothing-shopping context; market and service subtypes are secondary context.",
        "vegetable_fruit": "Mapped market context is the closest available category signal; retail and service subtypes are secondary context.",
        "general_goods": "Mapped retail activity is the closest available general-goods context; market and service subtypes are secondary context.",
    }
    rows = []
    for category, mapping in CATEGORY_GIS_FEATURE_WEIGHTS.items():
        for feature, weight in mapping.items():
            rows.append({
                "business_category": category,
                "mapping_status": "CATEGORY_SPECIFIC",
                "feature": feature,
                "feature_label": FEATURE_LABELS[feature],
                "within_commercial_factor_weight": weight,
                "saturation_scale": FEATURE_SCALES[feature],
                "rationale": rationale[category],
                "interpretation_limit": "Mapped environmental context only; not demand, footfall, sales or profitability.",
            })
    for category in sorted(FALLBACK_CATEGORIES):
        rows.append({
            "business_category": category,
            "mapping_status": "BASELINE_COMMERCIAL_FALLBACK",
            "feature": "baseline_commercial_factor",
            "feature_label": "Existing commercial, market and food POI mean",
            "within_commercial_factor_weight": 1.0,
            "saturation_scale": None,
            "rationale": "No sufficiently specific mapped feature exists for this category in the active snapshot.",
            "interpretation_limit": "Fallback preserves current production evidence and avoids an invented category signal.",
        })
    return pd.DataFrame(rows)


def result_rows(
    scored: pd.DataFrame,
    *,
    model: str,
    division: str,
    business: str,
    profile: str,
) -> list[dict[str, object]]:
    rows = []
    eligible_count = int(scored.score.notna().sum())
    weights = scored.attrs["effective_factor_weights"]
    for rank, (_, row) in enumerate(scored.loc[scored.score.notna()].head(3).iterrows(), start=1):
        item = {
            "scenario_id": f"{division}|{business}|{profile}",
            "model": model,
            "division": division,
            "business_category": business,
            "priority_profile": profile,
            "eligible_candidate_count": eligible_count,
            "rank": rank,
            "zone_id": row.zone_id,
            "suitability_score": row.score,
            "historical_business_compatibility": row.business_score,
            "category_gis_compatibility": row.get("category_gis_compatibility_score"),
            "commercial_score": row.commercial_score,
            "accessibility_score": row.access_score,
            "facilities_score": row.facilities_score,
            "historical_evidence_score": row.historical_score,
            "available_capacity": row.get("available_capacity"),
            "category_gis_fallback_used": row.get("category_gis_fallback_used"),
        }
        for factor, weight in weights.items():
            item[f"effective_weight_{factor}"] = weight
        for feature in AUDIT_FEATURES:
            item[feature] = row.get(feature)
        rows.append(item)
    return rows


def aggregate_comparison(comparison: pd.DataFrame, field: str) -> pd.DataFrame:
    return (
        comparison.groupby(field, as_index=False)
        .agg(
            scenario_count=("scenario_id", "size"),
            changed_first_rank_count=("first_rank_changed", "sum"),
            changed_first_rank_share=("first_rank_changed", "mean"),
            mean_top3_overlap=("top3_overlap_count", lambda values: float(np.mean(values) / 3.0)),
            mean_changed_top3_memberships=("changed_top3_membership_count", "mean"),
            mean_top10_position_changes=("top10_position_changes", "mean"),
            mean_score_change=("mean_score_change_common_candidates", "mean"),
            baseline_selected_category_gis_mean=("baseline_top3_category_gis_mean", "mean"),
            experimental_selected_category_gis_mean=("experimental_top3_category_gis_mean", "mean"),
            category_gis_selected_delta=("selected_category_gis_delta", "mean"),
        )
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    candidate_path = dataset_path("candidate_zones")
    vendor_path = dataset_path("vendor_registry")
    candidate = pd.read_csv(candidate_path, dtype={"zone_id": str})
    vendors = pd.read_csv(vendor_path, dtype={"vendor_id": str})

    if CATALOG.get("active_model_version") != "manual-142-v2":
        raise ValueError("The experiment requires active manual-142-v2")
    if len(candidate) != 166 or len(vendors) != 7259:
        raise ValueError("Active candidate or historical registry population changed")

    feature_report = feature_availability(candidate)
    mapping = mapping_report()

    # One read-only operational snapshot. All 96 scenarios reuse deep copies.
    live_zones, historical_vendors = mcda.load(
        use_live_status=True,
        database_path=DATABASE_PATH,
    )

    def frozen_load(use_live_status=False, database_path=None):
        return live_zones.copy(deep=True), historical_vendors.copy(deep=True)

    detailed_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    sensitivity_source: list[dict[str, object]] = []

    with patch.object(mcda, "load", frozen_load):
        for division in DIVISIONS:
            for business in BUSINESSES:
                for profile in PROFILES:
                    weight_profile = derive_mcda_weights({"priority_profile": profile})
                    weights = weight_profile["final_weights"]
                    baseline = mcda.score_candidates(
                        business,
                        division=division,
                        use_live_status=True,
                        database_path=DATABASE_PATH,
                        factor_weights=weights,
                        business_aware_experiment=False,
                    )
                    experiment = mcda.score_candidates(
                        business,
                        division=division,
                        use_live_status=True,
                        database_path=DATABASE_PATH,
                        factor_weights=weights,
                        business_aware_experiment=True,
                    )
                    if set(baseline.zone_id) != set(experiment.zone_id):
                        raise AssertionError("Experiment changed eligibility")
                    if not baseline.zone_division.eq(division).all() or not experiment.zone_division.eq(division).all():
                        raise AssertionError("Strict division filtering changed")
                    baseline_by_id = baseline.set_index("zone_id")
                    experiment_by_id = experiment.set_index("zone_id")
                    common_ids = baseline_by_id.index.intersection(experiment_by_id.index)
                    for unchanged_factor in ("business", "access", "facilities", "historical", "preference"):
                        if not np.allclose(
                            baseline_by_id.loc[common_ids, f"{unchanged_factor}_score"],
                            experiment_by_id.loc[common_ids, f"{unchanged_factor}_score"],
                            equal_nan=True,
                        ):
                            raise AssertionError(
                                f"Experiment unexpectedly changed {unchanged_factor} factor"
                            )
                    if baseline.attrs["effective_factor_weights"] != experiment.attrs["effective_factor_weights"]:
                        raise AssertionError("Experiment changed effective MCDA weights")

                    detailed_rows.extend(result_rows(
                        baseline, model="BASELINE", division=division,
                        business=business, profile=profile,
                    ))
                    detailed_rows.extend(result_rows(
                        experiment, model="BUSINESS_AWARE_EXPERIMENT", division=division,
                        business=business, profile=profile,
                    ))

                    baseline_top3 = _ids(baseline, 3)
                    experiment_top3 = _ids(experiment, 3)
                    baseline_top10 = _ids(baseline, 10)
                    experiment_top10 = _ids(experiment, 10)
                    baseline_scores = baseline.set_index("zone_id").score
                    experiment_scores = experiment.set_index("zone_id").score
                    common = baseline_scores.index.intersection(experiment_scores.index)
                    baseline_signal = experiment_by_id.reindex(baseline_top3).category_gis_compatibility_score
                    experimental_signal = experiment_by_id.reindex(experiment_top3).category_gis_compatibility_score
                    scenario_id = f"{division}|{business}|{profile}"
                    comparison_rows.append({
                        "scenario_id": scenario_id,
                        "division": division,
                        "business_category": business,
                        "priority_profile": profile,
                        "baseline_eligible_candidate_count": int(baseline.score.notna().sum()),
                        "experimental_eligible_candidate_count": int(experiment.score.notna().sum()),
                        "baseline_top3_zone_ids": "|".join(baseline_top3),
                        "experimental_top3_zone_ids": "|".join(experiment_top3),
                        "top3_overlap_count": len(set(baseline_top3) & set(experiment_top3)),
                        "changed_top3_membership_count": len(set(baseline_top3) ^ set(experiment_top3)),
                        "first_rank_changed": bool(baseline_top3 and experiment_top3 and baseline_top3[0] != experiment_top3[0]),
                        "baseline_top10_zone_ids": "|".join(baseline_top10),
                        "experimental_top10_zone_ids": "|".join(experiment_top10),
                        "top10_membership_overlap_count": len(set(baseline_top10) & set(experiment_top10)),
                        "top10_position_changes": sum(
                            1 for index in range(min(len(baseline_top10), len(experiment_top10)))
                            if baseline_top10[index] != experiment_top10[index]
                        ) + abs(len(baseline_top10) - len(experiment_top10)),
                        "mean_score_change_common_candidates": float((experiment_scores.loc[common] - baseline_scores.loc[common]).mean()),
                        "mean_absolute_score_change_common_candidates": float((experiment_scores.loc[common] - baseline_scores.loc[common]).abs().mean()),
                        "baseline_top3_category_gis_mean": _mean(baseline_signal),
                        "experimental_top3_category_gis_mean": _mean(experimental_signal),
                        "selected_category_gis_delta": (_mean(experimental_signal) or 0.0) - (_mean(baseline_signal) or 0.0),
                    })
                    for model, frame in (("BASELINE", baseline), ("BUSINESS_AWARE_EXPERIMENT", experiment)):
                        sensitivity_source.append({
                            "model": model,
                            "division": division,
                            "business_category": business,
                            "priority_profile": profile,
                            "top1_zone_id": (_ids(frame, 1) or [None])[0],
                            "top3_set": set(_ids(frame, 3)),
                        })

    detailed = pd.DataFrame(detailed_rows)
    comparison = pd.DataFrame(comparison_rows)
    division_summary = aggregate_comparison(comparison, "division")
    category_summary = aggregate_comparison(comparison, "business_category")

    sensitivity_rows = []
    sensitivity_frame = pd.DataFrame(sensitivity_source)
    for (model, division, business), group in sensitivity_frame.groupby(["model", "division", "business_category"]):
        sets = group.top3_set.tolist()
        sensitivity_rows.append({
            "model": model,
            "division": division,
            "business_category": business,
            "priority_profiles_evaluated": len(group),
            "unique_first_rank_zones_across_profiles": group.top1_zone_id.nunique(dropna=True),
            "unique_top3_zones_across_profiles": len(set().union(*sets)) if sets else 0,
            "mean_pairwise_top3_overlap_share": _pairwise_top3_overlap(sets),
        })
    sensitivity = pd.DataFrame(sensitivity_rows)

    category_sensitivity_rows = []
    for (model, division, profile), group in sensitivity_frame.groupby(["model", "division", "priority_profile"]):
        sets = group.top3_set.tolist()
        category_sensitivity_rows.append({
            "model": model,
            "division": division,
            "priority_profile": profile,
            "business_categories_evaluated": len(group),
            "unique_first_rank_zones_across_categories": group.top1_zone_id.nunique(dropna=True),
            "unique_top3_membership_sets_across_categories": len({frozenset(value) for value in sets}),
            "unique_zones_across_category_top3_results": len(set().union(*sets)) if sets else 0,
            "mean_pairwise_top3_overlap_share_across_categories": _pairwise_top3_overlap(sets),
        })
    category_sensitivity = pd.DataFrame(category_sensitivity_rows)

    feature_report.to_csv(OUT / "feature_availability.csv", index=False)
    mapping.to_csv(OUT / "category_gis_mapping.csv", index=False)
    detailed.to_csv(OUT / "scenario_results.csv", index=False)
    comparison.to_csv(OUT / "scenario_comparison.csv", index=False)
    division_summary.to_csv(OUT / "division_comparison.csv", index=False)
    category_summary.to_csv(OUT / "category_comparison.csv", index=False)
    sensitivity.to_csv(OUT / "preference_sensitivity.csv", index=False)
    category_sensitivity.to_csv(OUT / "business_category_sensitivity.csv", index=False)

    changed_first = int(comparison.first_rank_changed.sum())
    scenarios_changed = int(comparison.changed_top3_membership_count.gt(0).sum())
    overall_overlap = float(comparison.top3_overlap_count.mean() / 3.0)
    category_signal_delta = float(comparison.selected_category_gis_delta.mean())
    cross_category = category_sensitivity.pivot(
        index=["division", "priority_profile"],
        columns="model",
        values="mean_pairwise_top3_overlap_share_across_categories",
    )
    baseline_category_overlap = float(cross_category["BASELINE"].mean())
    experimental_category_overlap = float(cross_category["BUSINESS_AWARE_EXPERIMENT"].mean())
    more_differentiated_groups = int(
        cross_category["BUSINESS_AWARE_EXPERIMENT"].lt(cross_category["BASELINE"] - 1e-12).sum()
    )
    weak_features = feature_report.loc[
        feature_report.used_by_experiment & feature_report.nonzero_rows.lt(len(candidate) * 0.25),
        "feature",
    ].tolist()
    recommendation = (
        "DO_NOT_ACTIVATE_WITHOUT_EXPERT REVIEW"
        if weak_features or overall_overlap < 0.50
        else "ELIGIBLE_FOR_CONTROLLED REVIEW; DO NOT ACTIVATE YET"
    )

    lines = [
        "# Business-aware GIS MCDA experiment",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Active dataset: `{CATALOG.get('active_model_version')}`",
        f"Experimental policy: `{POLICY_VERSION}`",
        "Production feature flag default: `false`",
        "",
        "## Formula",
        "",
        "The experiment keeps the six existing MCDA factors and all effective weights. It replaces only the Commercial factor with a category-specific weighted mean of available mapped commercial-context features. Missing components are omitted with weight renormalization. Rows with no mapped category components fall back to the unchanged baseline Commercial score.",
        "",
        "Historical Business Compatibility remains an independent smoothed historical concentration score. Accessibility, pedestrian/transport context and Facilities remain separate factors and are not copied into category GIS compatibility. This is the main double-counting control.",
        "",
        "The category mapping uses commercial subtype counts rather than combining them with the aggregate commercial POI count. The aggregate contains those subtypes and would otherwise reward some mapped POIs twice.",
        "",
        "## 96-scenario comparison",
        "",
        f"- Changed first-ranked zone: {changed_first} of {len(comparison)} scenarios.",
        f"- Changed Top-3 membership: {scenarios_changed} of {len(comparison)} scenarios.",
        f"- Mean Top-3 overlap: {overall_overlap:.1%}.",
        f"- Mean change in selected category-GIS compatibility: {category_signal_delta:+.4f} on the 0-1 component scale.",
        f"- Mean absolute candidate score change: {comparison.mean_absolute_score_change_common_candidates.mean():.3f} points on the 0-100 scale.",
        f"- Mean cross-category Top-3 overlap changed from {baseline_category_overlap:.1%} to {experimental_category_overlap:.1%}.",
        f"- Category differentiation increased in {more_differentiated_groups} of 24 division/profile groups.",
        "",
        "## Evidence quality and limitations",
        "",
        f"- Sparse category features with nonzero coverage below 25% of candidate rows: {', '.join(weak_features) if weak_features else 'none'}.",
        "- Mapped POIs indicate environmental context only. They do not demonstrate demand, customer footfall, sales, profitability or legal suitability.",
        "- Historical association evidence is contextual and is not a success label.",
        "- The feature mapping is a transparent hypothesis and has not been calibrated with outcome or expert-judgement data.",
        "- Flower, other and unknown categories retain the baseline Commercial factor because no sufficiently specific active GIS field exists.",
        "- Operational capacity was read as a frozen snapshot. No PostgreSQL write path was called.",
        "",
        "## Activation recommendation",
        "",
        f"**{recommendation}.**",
        "",
        "Keep `BUSINESS_AWARE_MCDA_EXPERIMENT=false` in normal environments. Review the mapping with municipal/GIS domain experts, inspect sparse-feature zones, and repeat the isolated test and 96-scenario audit before any versioned catalog or production-policy change.",
    ]
    (OUT / "evaluation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if len(comparison) != 96:
        raise AssertionError("Expected exactly 96 scenario comparisons")
    if len(detailed.groupby(["scenario_id", "model"])) != 192:
        raise AssertionError("Expected baseline and experimental results for every scenario")
    if not detailed.suitability_score.between(0, 100).all():
        raise AssertionError("Suitability scores left the 0-100 range")
    if not comparison.baseline_eligible_candidate_count.eq(comparison.experimental_eligible_candidate_count).all():
        raise AssertionError("Experiment changed candidate eligibility")

    print(json.dumps({
        "scenarios": len(comparison),
        "changed_first_rank": changed_first,
        "changed_top3_scenarios": scenarios_changed,
        "mean_top3_overlap": overall_overlap,
        "mean_absolute_score_change": float(comparison.mean_absolute_score_change_common_candidates.mean()),
        "recommendation": recommendation,
        "output": str(OUT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
