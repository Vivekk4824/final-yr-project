"""Reproduce the final six-input audit against the active model and a read-only snapshot."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from itertools import product
from pathlib import Path
import sqlite3
import statistics
import sys
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.recommendation.business_aware_mcda import CATEGORY_GIS_FEATURE_WEIGHTS, FEATURE_SCALES
from backend.core.data_paths import CATALOG, dataset_path
from backend.recommendation.decision_policy import FACTOR_ORDER, active_mcda_configuration, derive_mcda_weights, normalize_weights
from backend.recommendation.location_ranking import DISTANCE_RADII_KM, LocationRankingPolicy, apply_location_ranking, reviewed_coordinates
from backend.recommendation.mcda_engine import rank_candidates, score_candidates
from backend.repositories.database import get_live_zone_status_map
from backend.services.eligibility import zone_ineligibility_reason

CATEGORIES = ("food", "clothing", "vegetable_fruit", "flower", "general_goods", "other")
PRIORITIES = ("BALANCED", "COMMERCIAL", "ACCESSIBILITY", "FACILITIES")
FACILITY_KEYS = ("market_preference", "transport_preference", "parking_preference")
FACILITY_FACTORS = ("commercial", "access", "facilities")
POLICY = LocationRankingPolicy()
FACILITY_TRIAL_MULTIPLIER = 3.3
REPORT_DIR = ROOT / "extra/reports/vendormap"


@dataclass(frozen=True)
class Profile:
    business: str = "food"
    division: str = "Nashik West"
    pin: str = ""
    radius_km: int | None = None
    priority: str = "BALANCED"
    facilities: tuple[bool, bool, bool] = (False, False, False)

    def weights(self, facility_trial=False):
        policy = derive_mcda_weights({
            "priority_profile": self.priority,
            **dict(zip(FACILITY_KEYS, self.facilities)),
        })
        if not facility_trial:
            return policy["final_weights"]
        config = active_mcda_configuration()
        base = policy["base_weights"]
        multipliers = dict(policy["multipliers"])
        for checked, factor in zip(self.facilities, FACILITY_FACTORS):
            if checked:
                multipliers[factor] = FACILITY_TRIAL_MULTIPLIER
        adjusted = normalize_weights({factor: base[factor] * multipliers[factor] for factor in FACTOR_ORDER})
        return normalize_weights({
            factor: config["baseline_blend"] * base[factor] + config["priority_blend"] * adjusted[factor]
            for factor in FACTOR_ORDER
        })


def plan(anchors):
    west = Profile(pin="NW_F_004")
    for division, business, priority in product(sorted(anchors), CATEGORIES, PRIORITIES):
        pin = anchors[division][CATEGORIES.index(business) % 2]
        yield "Matrix", Profile(business, division, pin, None, priority), None, False
    for category in CATEGORIES:
        yield "Business", replace(west, business=category), west, False
    for division in ("", *sorted(anchors)):
        yield "Division", replace(west, division=division), replace(west, division=""), False
    for pin in ("", "NW_F_004", "NW_F_025"):
        yield "Pin", replace(west, pin=pin), replace(west, pin=""), False
    for radius in (None, *DISTANCE_RADII_KM):
        yield "Radius", replace(west, radius_km=radius), west, False
    nearby_control = replace(west, pin="NW_F_009")
    yield "Radius", nearby_control, nearby_control, False
    shortfall = replace(nearby_control, radius_km=1)
    yield "Radius", shortfall, nearby_control, False
    yield "Expand Search", shortfall, shortfall, True
    for division, pins in anchors.items():
        for pin in ("", west.pin if division == west.division else pins[0]):
            control = Profile(division=division, pin=pin)
            for priority in PRIORITIES:
                yield "Priority", replace(control, priority=priority), control, False
    for priority, facility in zip(PRIORITIES[1:], (0, 1, 2)):
        control = replace(west, priority=priority)
        yield "Already prioritized", replace(control, facilities=tuple(i == facility for i in range(3))), control, False
    facility_sets = [(False, False, False), (True, False, False),
                     (False, True, False), (False, False, True), (True, True, True)]
    for division, pins in anchors.items():
        control = Profile(division=division, pin=west.pin if division == west.division else pins[0])
        for toggles in facility_sets:
            yield "Facilities", replace(control, facilities=toggles), control, False
            if any(toggles):
                yield "Facility trial", replace(control, facilities=toggles), control, False
    yield "Demo", Profile("vegetable_fruit", "Satpur", "SAT_F_020", None, "FACILITIES",
                          (False, False, True)), None, False


def displayed_records(frame):
    fields = [
        "zone_id", "original_mcda_score", "score", "personalized_score", "distance_km",
        "proximity_score", "proximity_contribution", "category_gis_method", "category_gis_features_used",
        "category_gis_compatibility_score", "available_capacity",
        *[f"{factor}_contribution" for factor in FACTOR_ORDER],
    ]
    return json.loads(frame.reindex(columns=fields).to_json(orient="records", double_precision=12))


def mean(records, field):
    return statistics.fmean(row[field] for row in records) if records else None


def causes(group, before, after, old_ids, new_ids):
    if group == "Division" and set(old_ids) != set(new_ids):
        return "Strict division eligibility changed the candidate set."
    if group in {"Radius", "Expand Search"} and old_ids != new_ids:
        return "The radius changed shortlist membership while leaving common scores intact."
    if not old_ids or not new_ids:
        return "The shortlist contains no eligible scored match."
    new_zone = new_ids[0] if old_ids[0] != new_ids[0] else next((zone for zone in new_ids if zone not in old_ids), new_ids[0])
    old_zone = old_ids[0] if old_ids[0] != new_ids[0] else next((zone for zone in old_ids if zone not in new_ids), old_ids[0])
    if not {new_zone, old_zone} <= set(before.index) & set(after.index):
        return "Eligibility changed the available candidates."

    def margin(frame, factor):
        return float(frame.at[new_zone, factor] - (frame.at[old_zone, factor] if new_zone != old_zone else 0))

    columns = [f"{factor}_contribution" for factor in FACTOR_ORDER] + ["proximity_contribution"]
    shifts = [(key.removesuffix("_contribution"), margin(after, key) - margin(before, key)) for key in columns]
    leading = sorted(((key, value) for key, value in shifts if np.isfinite(value) and abs(value) > 1e-8),
                     key=lambda item: abs(item[1]), reverse=True)[:3]
    scope = f"{new_zone} versus {old_zone}" if new_zone != old_zone else new_zone
    if not leading:
        return "The control and tested input produce the same ranking and factor contributions."
    return scope + " score-change drivers · " + ", ".join(f"{key} {value:+.3f} pts" for key, value in leading)


def audit(database):
    assert CATALOG["active_model_version"] == "manual-142-v2"
    live = get_live_zone_status_map(database)
    official = pd.read_csv(dataset_path("official_zones"))
    excluded = {
        row.zone_id: zone_ineligibility_reason(row.zone_type, live.get(row.zone_id))
        for row in official.itertuples() if row.zone_type == "FREE"
    }
    eligible = {zone for zone, reason in excluded.items() if reason is None}
    official_divisions = official.set_index("zone_id")["division"].to_dict()

    @lru_cache(maxsize=None)
    def scores(profile, category_gis, facility_trial=False):
        frame = score_candidates(
            profile.business, profile.division, use_live_status=True, database_path=database,
            include_unscorable=True, factor_weights=profile.weights(facility_trial), business_aware_experiment=category_gis,
        )
        assert set(frame.zone_id) == {
            zone for zone in eligible if not profile.division or official_divisions[zone] == profile.division
        }
        return frame

    city = scores(Profile(division=""), False)
    coordinates = reviewed_coordinates(city)
    pins = city[["zone_id", "zone_division"]].join(coordinates).dropna()
    anchors = {division: (group.zone_id.iloc[0], group.zone_id.iloc[-1])
               for division, group in pins.sort_values(["longitude", "zone_id"]).groupby("zone_division")}
    locations = pins.set_index("zone_id")[["latitude", "longitude"]]

    @lru_cache(maxsize=None)
    def ranked(profile, category_gis=True, proximity=True, expanded=False, facility_trial=False):
        settings = replace(profile, pin="", radius_km=None)
        raw = scores(settings, category_gis, facility_trial)
        frame = raw.copy()
        frame["distance_km"] = np.nan
        frame["personalized_score"] = frame["score"]
        frame["proximity_contribution"] = 0.0
        if profile.pin and proximity:
            point = tuple(locations.loc[profile.pin])
            frame = apply_location_ranking(frame, point, POLICY)
            frame["proximity_contribution"] = POLICY.proximity_weight * frame.proximity_score.fillna(0)
            for factor in FACTOR_ORDER:
                frame[f"{factor}_contribution"] *= np.where(frame.personalized_score.notna(), 1 - POLICY.proximity_weight, 1)
            known = frame.personalized_score.notna()
            assert np.allclose(frame.loc[known, "personalized_score"],
                               .85 * frame.loc[known, "score"] + .15 * frame.loc[known, "proximity_score"])
            assert frame.loc[frame.distance_km.isna(), "personalized_score"].isna().all()
        assert frame.loc[frame.score.isna(), "personalized_score"].isna().all()
        shortlist = frame
        if proximity and profile.pin and profile.radius_km is not None and not expanded:
            shortlist = frame.loc[frame.distance_km.le(profile.radius_km)]
        top = rank_candidates(shortlist)
        assert all(live[zone]["status"] == "OPEN" and live[zone]["available_capacity"] > 0 for zone in top.zone_id)
        if profile.division:
            assert top.zone_division.eq(profile.division).all()
        feasible = raw.loc[raw.zone_id.isin(shortlist.zone_id)].sort_values(
            ["original_mcda_score", "zone_id"], ascending=[False, True]
        )
        return frame.set_index("zone_id"), top, feasible.head(len(top))

    output = []
    for number, (group, profile, control, expanded) in enumerate(plan(anchors), 1):
        trial = group == "Facility trial"
        after, top, feasible = ranked(profile, expanded=expanded, facility_trial=trial)
        reference, baseline_top, _ = ranked(profile, category_gis=False, proximity=False)
        before = reference
        if control is None:
            previous = baseline_top
        else:
            before, previous, _ = ranked(control)
        prior_records, records = displayed_records(previous), displayed_records(top)
        for record in records:
            record["approved_original_mcda_score"] = float(reference.at[record["zone_id"], "original_mcda_score"])
        before_ids, ids = previous.zone_id.tolist(), top.zone_id.tolist()
        original = mean(records, "original_mcda_score")
        same_count_baseline = displayed_records(baseline_top.head(len(top)))
        approved_original_mean = float(reference.loc[ids, "original_mcda_score"].mean()) if records else None
        loss = mean(same_count_baseline, "original_mcda_score") - approved_original_mean if records else None
        feasible_loss = feasible.original_mcda_score.mean() - original if records else None
        original_change = original - mean(prior_records, "original_mcda_score") if records and prior_records else None
        ranking_change = mean(records, "personalized_score") - mean(prior_records, "personalized_score") if records and prior_records else None
        point = tuple(locations.loc[profile.pin]) if profile.pin else (None, None)
        if group == "Radius" or expanded:
            common = before.index.intersection(after.index)
            assert before.loc[common, ["original_mcda_score", "personalized_score"]].equals(
                after.loc[common, ["original_mcda_score", "personalized_score"]]
            )
        if group == "Priority" and profile.priority != "BALANCED":
            factor = {"COMMERCIAL": "commercial", "ACCESSIBILITY": "access", "FACILITIES": "facilities"}[profile.priority]
            assert top.attrs["effective_factor_weights"][factor] > previous.attrs["effective_factor_weights"][factor]
        if group in {"Facilities", "Facility trial"}:
            for checked, factor in zip(profile.facilities, FACILITY_FACTORS):
                if checked:
                    assert top.attrs["effective_factor_weights"][factor] > previous.attrs["effective_factor_weights"][factor]
        if group == "Already prioritized":
            assert top.attrs["effective_factor_weights"] == previous.attrs["effective_factor_weights"]
            assert ids == before_ids
        if group == "Business":
            if profile.business in CATEGORY_GIS_FEATURE_WEIGHTS:
                assert after.category_gis_method.eq("CATEGORY_GIS_WEIGHTED_COMMERCIAL_REPLACEMENT").any()
            else:
                assert after.category_gis_fallback_used.all()
        location_only = ranked(profile, category_gis=False, expanded=expanded, facility_trial=trial)[1]
        category_gain = None
        if profile.business in CATEGORY_GIS_FEATURE_WEIGHTS and records and len(location_only):
            evidence = after.category_gis_compatibility_score
            category_gain = float(evidence.loc[ids].mean() - evidence.loc[location_only.zone_id].mean())
        output.append({
            "scenario_id": f"S{number:03}", "group": group, "business": profile.business,
            "division": profile.division or "Any", "pin_reference": profile.pin,
            "latitude": point[0], "longitude": point[1], "radius_km": profile.radius_km,
            "expanded": expanded, "priority": profile.priority, **dict(zip(FACILITY_KEYS, profile.facilities)),
            "comparison_profile": asdict(control or profile),
            "comparison_policy": "flag_off_baseline" if control is None else "matched_input_control",
            "facility_multiplier": FACILITY_TRIAL_MULTIPLIER if trial else active_mcda_configuration()["high_multiplier"],
            "effective_weights": top.attrs["effective_factor_weights"],
            "previous_weights": previous.attrs["effective_factor_weights"],
            "previous_top_3": before_ids, "top_3": ids, "previous_results": prior_records, "results": records,
            "unmodified_policy_results": displayed_records(baseline_top),
            "top_1_changed": before_ids[:1] != ids[:1], "top_3_changed": set(before_ids) != set(ids),
            "original_top_3_mean_change": original_change, "rank_score_mean_change": ranking_change,
            "approved_original_score_mean": approved_original_mean,
            "original_loss_vs_unrestricted_baseline": loss, "original_loss_within_shortlist": feasible_loss,
            "category_gis_gain_vs_location_only": category_gain,
            "eligible_scoreable": int(after.score.notna().sum()),
            "shortlist_count": len(ids), "can_expand": bool(profile.pin and profile.radius_km and len(ids) < 3 and not expanded),
            "drivers": causes(group, before, after, before_ids, ids),
        })
    near = next(row for row in output if row["group"] == "Radius" and row["pin_reference"] == "NW_F_009" and row["radius_km"] == 1)
    expanded = next(row for row in output if row["expanded"])
    assert near["can_expand"] and expanded["shortlist_count"] == 3

    grouped = defaultdict(list)
    for row in output:
        grouped[row["group"]].append(row)
    summary = {}
    for group, rows in grouped.items():
        losses = [row["original_loss_vs_unrestricted_baseline"] for row in rows
                  if row["original_loss_vs_unrestricted_baseline"] is not None]
        gains = [row["category_gis_gain_vs_location_only"] for row in rows
                 if row["category_gis_gain_vs_location_only"] is not None]
        summary[group] = dict(scenarios=len(rows), top_1_changed=sum(row["top_1_changed"] for row in rows),
                              top_3_changed=sum(row["top_3_changed"] for row in rows),
                              mean_original_loss=statistics.fmean(losses),
                              mean_category_gis_gain=statistics.fmean(gains) if gains else None)
    details = {
        "groups": summary,
        "official_free": len(excluded), "eligible_free": len(eligible),
        "excluded": {zone: {"reason": reason, "status": live[zone]["status"]} for zone, reason in excluded.items() if reason},
        "unscorable": int(city.score.isna().sum()), "no_reviewed_coordinates": int(coordinates.latitude.isna().sum()),
        "missing_gis_rows": {key: int(city[key].isna().sum()) for key in FEATURE_SCALES},
    }
    return output, details


if __name__ == "__main__":
    with TemporaryDirectory(prefix="vendormap-input-audit-") as directory:
        copy = Path(directory) / "snapshot.db"
        source = dataset_path("database").resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source, uri=True)) as existing, closing(sqlite3.connect(copy)) as snapshot:
            existing.backup(snapshot)
        rows, summary = audit(copy)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "final-recommendation-input-validation.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, rows[0].keys())
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False, allow_nan=False)
                          if isinstance(value, (dict, list)) else value for key, value in row.items()} for row in rows)
    print(json.dumps(summary, indent=2, allow_nan=False))
