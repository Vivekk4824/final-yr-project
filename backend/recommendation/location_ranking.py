"""Experimental proximity ranking using saved references from the active model."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from typing import Mapping

import numpy as np
import pandas as pd

from backend.core.data_paths import dataset_path
from backend.geo.zone_locations import METRIC_CRS, TO_WGS84

REVIEWED_REFERENCE_SOURCES = {"MANUAL_PROVISIONAL", "PILOT_SAVED_PROVISIONAL"}
DISTANCE_RADII_KM = (1, 3, 5, 10)
DEFAULT_PROXIMITY_WEIGHT = 0.15
DEFAULT_DECAY_KM = 3.0
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocationRankingPolicy:
    proximity_weight: float = DEFAULT_PROXIMITY_WEIGHT
    decay_km: float = DEFAULT_DECAY_KM

    def __post_init__(self):
        if not 0 <= self.proximity_weight <= 1:
            raise ValueError("LOCATION_PROXIMITY_WEIGHT must be between 0 and 1")
        if not math.isfinite(self.decay_km) or self.decay_km <= 0:
            raise ValueError("LOCATION_PROXIMITY_DECAY_KM must be positive and finite")


def configured_location_policy() -> LocationRankingPolicy | None:
    flag = os.getenv("LOCATION_RANKING_EXPERIMENT", "false").strip().lower()
    if flag not in {"true", "false"}:
        raise ValueError("LOCATION_RANKING_EXPERIMENT must be true or false")
    if flag == "false":
        return None
    return LocationRankingPolicy(
        proximity_weight=float(os.getenv("LOCATION_PROXIMITY_WEIGHT", str(DEFAULT_PROXIMITY_WEIGHT))),
        decay_km=float(os.getenv("LOCATION_PROXIMITY_DECAY_KM", str(DEFAULT_DECAY_KM))),
    )


def saved_working_location(profile: Mapping) -> tuple[float, float] | None:
    latitude = profile.get("preferred_latitude")
    longitude = profile.get("preferred_longitude")
    if (
        type(latitude) in (int, float) and -90 <= latitude <= 90
        and type(longitude) in (int, float) and -180 <= longitude <= 180
    ):
        return latitude, longitude
    return None


def reviewed_coordinates(zones: pd.DataFrame) -> pd.DataFrame:
    """Read the stored model reference in its recorded CRS and return WGS84."""
    coordinates = pd.DataFrame(np.nan, index=zones.index, columns=["latitude", "longitude"])
    if zones.empty or "reference_location_source" not in zones:
        return coordinates
    columns = [
        "zone_id", "reference_location_source", "feature_reference_crs",
        "reference_point_easting", "reference_point_northing",
    ]
    try:
        features = pd.read_csv(
            dataset_path("zone_features"), usecols=columns, dtype={"zone_id": str},
        ).set_index("zone_id")
        if not features.index.is_unique:
            raise ValueError("Duplicate zone distance references")
    except (OSError, ValueError) as exc:
        logger.warning("Active zone distance references unavailable (%s)", type(exc).__name__)
        return coordinates
    references = features.reindex(zones.zone_id.astype(str)).set_axis(zones.index)
    east = pd.to_numeric(references["reference_point_easting"], errors="coerce")
    north = pd.to_numeric(references["reference_point_northing"], errors="coerce")
    valid = (
        zones["reference_location_source"].isin(REVIEWED_REFERENCE_SOURCES)
        & references["reference_location_source"].eq(zones["reference_location_source"])
        & references["feature_reference_crs"].eq(METRIC_CRS)
        & np.isfinite(east) & np.isfinite(north)
    )
    if valid.any():
        longitudes, latitudes = TO_WGS84.transform(east[valid].to_numpy(), north[valid].to_numpy())
        coordinates.loc[valid, "latitude"] = latitudes
        coordinates.loc[valid, "longitude"] = longitudes
    return coordinates.where(coordinates.latitude.between(-90, 90) & coordinates.longitude.between(-180, 180))


def apply_location_ranking(
    scored: pd.DataFrame,
    location: tuple[float, float],
    policy: LocationRankingPolicy,
) -> pd.DataFrame:
    """Attach straight-line distance and order the complete eligible candidate list."""
    ranked = scored.copy()
    coordinates = reviewed_coordinates(ranked)
    latitude, longitude = np.radians(location)
    zone_latitude = np.radians(coordinates.latitude)
    zone_longitude = np.radians(coordinates.longitude)
    haversine = (
        np.sin((zone_latitude - latitude) / 2) ** 2
        + np.cos(latitude) * np.cos(zone_latitude) * np.sin((zone_longitude - longitude) / 2) ** 2
    )
    ranked["distance_km"] = 6371.0088 * 2 * np.arcsin(np.sqrt(haversine.clip(0, 1)))
    ranked["proximity_score"] = (100 * np.exp(-ranked.distance_km / policy.decay_km)).where(ranked.score.notna())
    base_score = (
        pd.to_numeric(ranked["personalized_score"], errors="coerce")
        if "personalized_score" in ranked
        else ranked.score
    )
    ranked["personalized_score"] = (
        (1 - policy.proximity_weight) * base_score + policy.proximity_weight * ranked.proximity_score
    ) if policy.proximity_weight else base_score
    sort_columns = ["personalized_score", "original_mcda_score", "zone_id"]
    ascending = [False, False, True]
    if "requirement_exact_match" in ranked:
        sort_columns.insert(0, "requirement_exact_match")
        ascending.insert(0, False)
    return ranked.sort_values(
        sort_columns,
        ascending=ascending,
        na_position="last",
    ).reset_index(drop=True)
