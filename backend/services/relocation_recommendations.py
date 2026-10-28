"""Read-only admin relocation alternatives built on the existing MCDA policy."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from backend.decision_policy import derive_mcda_weights
from backend.core.data_paths import CATALOG
from backend.geo.zone_locations import resolve_zone_locations
from backend.mcda_engine import recommend
from backend.repositories.database import (
    DATABASE_PATH,
    OperationalNotFoundError,
    OperationalValidationError,
    connect,
)
from backend.services.capacity_analysis import zone_capacity_analysis
from backend.services.historical_associations import get_association
from backend.services.vendors import get_vendor_profile


NEARBY_RADIUS_M = 3_000.0


def _active_allocation(vendor_id: str, database_path) -> dict[str, Any] | None:
    db = connect(database_path)
    try:
        row = db.execute(
            """SELECT allocation_id, vendor_id, zone_id, request_id, allocated_at,
                      allocation_source
               FROM allocations
               WHERE vendor_id = ? AND status = 'ACTIVE'""",
            (vendor_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        db.close()


def _distance_metres(source: dict[str, Any] | None, target: dict[str, Any] | None) -> float | None:
    if not source or not target:
        return None
    values = (source.get("easting"), source.get("northing"), target.get("easting"), target.get("northing"))
    if any(value is None for value in values):
        return None
    distance = math.hypot(float(values[2]) - float(values[0]), float(values[3]) - float(values[1]))
    return distance if math.isfinite(distance) else None


def relocation_recommendations(vendor_id: str, *, limit: int = 5, include_all: bool = False,
                               database_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    """Rank eligible alternatives without creating requests or allocations."""
    if limit < 1 or limit > 20:
        raise OperationalValidationError("limit must be between 1 and 20")
    profile = get_vendor_profile(vendor_id, database_path=database_path)
    if profile is None:
        raise OperationalNotFoundError(f"Unknown vendor_id: {vendor_id}")

    active = _active_allocation(vendor_id, database_path)
    association = get_association(vendor_id, database_path)
    if active:
        source_zone_id = active["zone_id"]
        source_type = (
            "IMPORTED_EXISTING_ALLOCATION"
            if active.get("allocation_source") == "LEGACY_IMPORT"
            else "ACTIVE_APPROVED_ALLOCATION"
        )
    elif association and association.get("accepted") and association.get("matched_zone_id"):
        source_zone_id, source_type = association["matched_zone_id"], "ACCEPTED_HISTORICAL_ASSOCIATION"
    else:
        raise OperationalValidationError(
            "Relocation alternatives require an active operational allocation or accepted historical source zone"
        )

    weight_profile = derive_mcda_weights(profile)
    engine_vendor_id = vendor_id if profile.get("vendor_type") != "NEW" else ""
    ranked = recommend(
        profile.get("business_category") or "",
        profile.get("preferred_division") or "",
        engine_vendor_id,
        top_n=min(limit, 20),
        use_live_status=True,
        database_path=database_path,
        factor_weights=weight_profile["final_weights"],
        include_all=True,
    )
    candidates = ranked.attrs.get("all_candidates", pd.DataFrame())
    candidates = candidates.loc[candidates.score.notna() & candidates.zone_id.ne(source_zone_id)].copy()
    capacity = zone_capacity_analysis(database_path)

    try:
        locations = resolve_zone_locations(database_path)
        source_location = locations.get(source_zone_id)
    except (ValueError, OSError):
        locations, source_location = {}, None

    alternatives = []
    for _, row in candidates.iterrows():
        zone_id = str(row["zone_id"])
        zone_capacity = capacity.get(zone_id, {})
        target_location = locations.get(zone_id)
        distance = _distance_metres(source_location, target_location)
        nearby = distance is not None and distance <= NEARBY_RADIUS_M
        if nearby:
            proximity_tier = "NEARBY_WITHIN_3_KM"
        elif distance is None:
            proximity_tier = "PROXIMITY_UNAVAILABLE"
        else:
            proximity_tier = "CITYWIDE_FALLBACK"
        operational_available = zone_capacity.get("operational_available")
        capacity_reason = (
            "Operational capacity is not listed"
            if operational_available is None
            else f"{operational_available} operational places available"
        )
        proximity_reason = (
            f"{distance / 1000:.2f} km from the source reference"
            if distance is not None
            else "Proximity unavailable because a usable source or target reference is missing"
        )
        alternatives.append({
            "zone_id": zone_id,
            "official_description": row.get("official_description"),
            "division": row.get("zone_division"),
            "zone_type": row.get("zone_type", "FREE"),
            "mcda_score": float(row["score"]),
            "distance_m": round(distance, 1) if distance is not None else None,
            "proximity_tier": proximity_tier,
            "location_source": target_location.get("location_source") if target_location else None,
            "operational_occupancy": zone_capacity.get("operational_occupancy"),
            "operational_available": operational_available,
            "planning_load": zone_capacity.get("planning_load"),
            "planning_available": zone_capacity.get("planning_available"),
            "planning_overcapacity": zone_capacity.get("planning_overcapacity"),
            "capacity_pressure_status": zone_capacity.get("capacity_pressure_status"),
            "reasons": [
                "Eligible FREE zone under the existing operational policy",
                f"Existing personalized MCDA suitability score: {float(row['score']):.2f}",
                proximity_reason,
                capacity_reason,
            ],
        })

    def suitability_key(item):
        distance = item["distance_m"] if item["distance_m"] is not None else float("inf")
        return (-item["mcda_score"], distance, item["zone_id"])

    nearby = sorted((item for item in alternatives if item["proximity_tier"] == "NEARBY_WITHIN_3_KM"), key=suitability_key)
    fallback = sorted((item for item in alternatives if item["proximity_tier"] != "NEARBY_WITHIN_3_KM"), key=suitability_key)
    ordered = nearby + fallback
    for index, item in enumerate(ordered, start=1):
        item["relocation_rank"] = index

    response = {
        "vendor_id": vendor_id,
        "source_zone_id": source_zone_id,
        "source_type": source_type,
        "nearby_radius_m": NEARBY_RADIUS_M,
        "proximity_available": source_location is not None,
        "recommendations": ordered[:limit],
        "eligible_alternative_count": len(ordered),
        "other_eligible_count": max(0, len(ordered) - limit),
        "model_version": CATALOG.get("active_model_version"),
        "notice": "Planning alternatives only. No request, allocation, slot, or vendor location was changed.",
    }
    if include_all:
        response["other_eligible_alternatives"] = ordered[limit:]
    return response

