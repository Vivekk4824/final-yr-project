"""Synthetic-demo vendor requirement compatibility ranking.

This module is isolated behind ``SYNTHETIC_ZONE_REQUIREMENTS`` because the
repository has no reviewed municipal operating-hours, stall-area, or fee data.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = ROOT / "data" / "demo" / "zone_requirement_profiles.csv"
SOURCE = "SYNTHETIC_DEMO_NOT_MUNICIPAL_DATA"
# Vendor-entered constraints must have enough influence to change the shortlist,
# rather than merely shaving a few points from the same globally strong zones.
REQUIREMENTS_WEIGHT = 0.45


def enabled() -> bool:
    raw = os.getenv("SYNTHETIC_ZONE_REQUIREMENTS", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise ValueError("SYNTHETIC_ZONE_REQUIREMENTS must be true or false")
    return raw == "true"


def apply_vendor_requirement_ranking(
    scored: pd.DataFrame,
    requirements: Mapping[str, object] | None,
) -> pd.DataFrame:
    """Attach three transparent compatibility scores and rerank candidates."""
    if not enabled() or not requirements or scored.empty:
        return scored
    requested_period = requirements.get("preferred_operating_period")
    requested_space = requirements.get("required_space_sqm")
    budget = requirements.get("max_monthly_budget")
    provided = [requested_period is not None, requested_space is not None, budget is not None]
    if not any(provided):
        return scored
    profiles = pd.read_csv(DEMO_PATH, dtype={"zone_id": str})
    if profiles.zone_id.duplicated().any() or not profiles.data_source.eq(SOURCE).all():
        raise ValueError("Invalid synthetic zone requirement profile")
    ranked = scored.merge(profiles, on="zone_id", how="left", validate="many_to_one")
    if ranked.data_source.isna().any():
        raise ValueError("Synthetic requirements do not cover every recommendation zone")

    if requested_period in (None, "FLEXIBLE"):
        ranked["operating_period_match_score"] = 1.0
    else:
        ranked["operating_period_match_score"] = ranked.allowed_operating_periods.map(
            lambda value: float(str(requested_period) in str(value).split("|"))
        )

    if requested_space is None:
        ranked["space_match_score"] = 1.0
    else:
        ranked["space_match_score"] = np.clip(
            ranked.available_stall_space_sqm / float(requested_space), 0.0, 1.0
        )

    if budget is None:
        ranked["budget_match_score"] = 1.0
    else:
        budget = float(budget)
        excess = np.maximum(ranked.monthly_fee - budget, 0.0)
        ranked["budget_match_score"] = np.exp(-excess / max(budget, 1.0))

    components = []
    if provided[0]:
        components.append(ranked.operating_period_match_score)
    if provided[1]:
        components.append(ranked.space_match_score)
    if provided[2]:
        components.append(ranked.budget_match_score)
    ranked["requirements_score"] = 100.0 * sum(components) / len(components)
    exact_checks = []
    if requested_period not in (None, "FLEXIBLE"):
        exact_checks.append(ranked.operating_period_match_score.eq(1.0))
    if requested_space is not None:
        exact_checks.append(ranked.available_stall_space_sqm.ge(float(requested_space)))
    if budget is not None:
        exact_checks.append(ranked.monthly_fee.le(float(budget)))
    ranked["requirement_exact_match"] = (
        pd.concat(exact_checks, axis=1).all(axis=1) if exact_checks
        else pd.Series(True, index=ranked.index)
    )
    ranked["requirement_match_count"] = (
        pd.concat(exact_checks, axis=1).sum(axis=1).astype(int) if exact_checks
        else pd.Series(0, index=ranked.index, dtype=int)
    )
    ranked["requirement_constraint_count"] = len(exact_checks)
    ranked["personalized_score"] = (
        (1.0 - REQUIREMENTS_WEIGHT) * ranked.score
        + REQUIREMENTS_WEIGHT * ranked.requirements_score
    ).where(ranked.score.notna())
    ranked["requirement_data_source"] = SOURCE
    ranked["synthetic_requirements_weight"] = REQUIREMENTS_WEIGHT
    ranked.attrs.update(scored.attrs)
    return ranked.sort_values(
        ["requirement_exact_match", "personalized_score", "original_mcda_score", "zone_id"],
        ascending=[False, False, False, True],
        na_position="last",
    ).reset_index(drop=True)
