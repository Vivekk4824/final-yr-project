"""Disabled-by-default business-aware GIS scoring experiment.

The experiment replaces the environmental ``commercial`` component with a
category-specific blend of existing mapped POI signals. It does not add a
seventh MCDA factor or alter historical business compatibility.
"""
from __future__ import annotations

import os
from typing import Mapping

import numpy as np
import pandas as pd


FEATURE_FLAG = "BUSINESS_AWARE_MCDA_EXPERIMENT"
POLICY_VERSION = "business-aware-gis-v1"

# Existing diminishing-return scales are retained. Retail uses the same
# conservative count scale as food POIs; none of these are fitted demand
# coefficients.
FEATURE_SCALES: dict[str, float] = {
    "market_poi_count_500m": 4.0,
    "food_poi_count_250m": 8.0,
    "retail_poi_count_250m": 8.0,
    "service_poi_count_250m": 8.0,
}

# Only commercial-context signals are used here. Road, pedestrian, transport
# and facilities stay in their existing factors so GIS evidence is not rewarded
# twice.
CATEGORY_GIS_FEATURE_WEIGHTS: dict[str, dict[str, float]] = {
    "food": {
        "food_poi_count_250m": 0.65,
        "market_poi_count_500m": 0.20,
        "service_poi_count_250m": 0.15,
    },
    "clothing": {
        "retail_poi_count_250m": 0.60,
        "market_poi_count_500m": 0.25,
        "service_poi_count_250m": 0.15,
    },
    "vegetable_fruit": {
        "market_poi_count_500m": 0.60,
        "retail_poi_count_250m": 0.25,
        "service_poi_count_250m": 0.15,
    },
    "general_goods": {
        "retail_poi_count_250m": 0.50,
        "market_poi_count_500m": 0.25,
        "service_poi_count_250m": 0.25,
    },
}

FALLBACK_CATEGORIES = {"flower", "other", "unknown"}

FEATURE_LABELS = {
    "commercial_poi_count_250m": "mapped commercial POIs within 250 m",
    "market_poi_count_500m": "mapped markets within 500 m",
    "food_poi_count_250m": "mapped food POIs within 250 m",
    "retail_poi_count_250m": "mapped retail POIs within 250 m",
    "service_poi_count_250m": "mapped service POIs within 250 m",
}


def experiment_enabled(explicit: bool | None = None) -> bool:
    """Resolve the feature flag without changing the default production path."""

    if explicit is not None:
        if not isinstance(explicit, bool):
            raise ValueError("business_aware_experiment must be boolean or None")
        return explicit

    raw = os.environ.get(FEATURE_FLAG, "false").strip().lower()
    if raw not in {"true", "false"}:
        raise ValueError(f"{FEATURE_FLAG} must be true or false")
    return raw == "true"


def _numeric_feature(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[name], errors="coerce")


def _saturation(values: pd.Series, scale: float) -> pd.Series:
    return np.clip(
        np.log1p(np.maximum(values, 0.0)) / np.log1p(scale),
        0.0,
        1.0,
    )


def category_gis_scores(
    zones: pd.DataFrame,
    business: str,
    baseline_commercial: pd.Series,
) -> dict[str, object]:
    """Return category-aware Commercial scores and auditable components.

    Missing mapped features are omitted and the remaining configured weights
    are renormalized. If none are available for a row, the unchanged baseline
    Commercial score is used for that row.
    """

    mapping = CATEGORY_GIS_FEATURE_WEIGHTS.get(business)
    baseline = pd.to_numeric(baseline_commercial, errors="coerce")

    if mapping is None:
        if business not in FALLBACK_CATEGORIES:
            raise ValueError("No category-aware GIS policy for business category")
        return {
            "score": baseline.copy(),
            "method": pd.Series("BASELINE_COMMERCIAL_FALLBACK", index=zones.index),
            "fallback": pd.Series(True, index=zones.index, dtype=bool),
            "features_used": "commercial_poi_count_250m|market_poi_count_500m|food_poi_count_250m",
            "components": {},
            "mapping": {},
        }

    numerator = pd.Series(0.0, index=zones.index, dtype=float)
    denominator = pd.Series(0.0, index=zones.index, dtype=float)
    components: dict[str, pd.Series] = {}

    for feature, weight in mapping.items():
        component = _saturation(_numeric_feature(zones, feature), FEATURE_SCALES[feature])
        components[feature] = component
        available = component.notna()
        numerator = numerator.add(component.fillna(0.0) * weight)
        denominator = denominator.add(available.astype(float) * weight)

    category_score = numerator / denominator.replace(0.0, np.nan)
    fallback = category_score.isna() & baseline.notna()
    score = category_score.where(~fallback, baseline)
    method = pd.Series("CATEGORY_GIS_WEIGHTED_COMMERCIAL_REPLACEMENT", index=zones.index)
    method = method.where(~fallback, "BASELINE_COMMERCIAL_MISSING_GIS_FALLBACK")

    return {
        "score": score,
        "method": method,
        "fallback": fallback,
        "features_used": "|".join(mapping),
        "components": components,
        "mapping": dict(mapping),
    }


def category_gis_evidence(record: Mapping[str, object]) -> list[dict[str, object]]:
    """Build cautious, source-grounded explanation evidence for one row."""

    business = str(record.get("requested_business_category") or "")
    mapping = CATEGORY_GIS_FEATURE_WEIGHTS.get(business, {})
    evidence: list[dict[str, object]] = []
    for feature, weight in mapping.items():
        value = record.get(feature)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(numeric):
            continue
        evidence.append({
            "label": FEATURE_LABELS[feature],
            "value": numeric,
            "configured_weight_percent": weight * 100.0,
        })
    return evidence
