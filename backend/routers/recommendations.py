"""Recommendations HTTP endpoints; existing contracts retained."""
from __future__ import annotations
from backend.core import context as dependencies
from fastapi import Request as FastAPIRequest
from fastapi import HTTPException
from backend.schemas.api import Request
from backend.recommendation.recommendation_evaluation import SensitivityConfig
from backend.schemas.api import SensitivityRequest
from backend.core.serialization import clean
from backend.recommendation.recommendation_evaluation import evaluate_weight_sensitivity
from backend.services.explanations import explain
from backend.recommendation.mcda_engine import recommend
import pandas as pd
from backend.core.data_paths import CATALOG, dataset_path
from backend.services.eligibility import zone_ineligibility_reason
from backend.repositories.database import get_live_zone_status_map
from backend.services.legacy_allocation_import import active_vendor_category_counts
from backend.services.recommendation_context import resolve_recommendation_context
from backend.services.ai_zone_explanations import generate_explanations
from backend.core.security import request_session
from backend.services.vendors import get_vendor_profile
from backend.repositories.database import get_active_allocation_for_vendor
from backend.recommendation.decision_policy import FACTOR_ORDER
from backend.recommendation.business_aware_mcda import CATEGORY_GIS_FEATURE_WEIGHTS
from backend.recommendation.location_ranking import DISTANCE_RADII_KM, configured_location_policy, saved_working_location
from backend.recommendation.vendor_requirement_ranking import enabled as requirement_ranking_enabled, SOURCE as REQUIREMENT_SOURCE
from backend.services.capacity_analysis import zone_capacity_analysis
from fastapi import APIRouter
router = APIRouter()

PERSONALIZED_FIELDS = (
    "original_mcda_score", "personalized_score", "distance_km", "proximity_score",
    "requested_business_category", "category_gis_method", "category_gis_fallback_used",
    "allowed_operating_periods", "available_stall_space_sqm", "monthly_fee",
    "operating_period_match_score", "space_match_score", "budget_match_score",
    "requirements_score", "requirement_data_source", "synthetic_requirements_weight",
    "requirement_exact_match", "requirement_match_count", "requirement_constraint_count",
)


def _ranking_reason(row):
    if pd.isna(row.get("score")):
        return {}
    category_features = CATEGORY_GIS_FEATURE_WEIGHTS.get(row.get("requested_business_category"), {})
    mapped = {
        feature: weight * value
        for feature, weight in category_features.items()
        if pd.notna(value := row.get(f"category_gis_component_{feature}")) and value > 0
    }
    if mapped:
        feature = max(mapped, key=mapped.get)
        return {"ranking_reason": {"kind": "mapped_poi", "feature": feature, "count": float(row[feature])}}
    if pd.notna(row.get("distance_km")) and row["distance_km"] <= 3:
        return {"ranking_reason": {"kind": "nearby"}}
    factors = [factor for factor in FACTOR_ORDER if pd.notna(row.get(f"{factor}_contribution"))]
    factor = max(factors, key=lambda item: row[f"{item}_contribution"]) if factors else None
    return {"ranking_reason": {"kind": "mcda_factor", "factor": factor}} if factor else {}


def _why_recommended(row, profile, business, division):
    """Return deterministic, source-grounded reasons for this vendor-zone pair."""
    reasons = []
    if business:
        reasons.append({
            "kind": "business_category",
            "value": business,
            "detail": (
                "CATEGORY_AWARE_GIS"
                if bool(row.get("business_aware_mcda_experiment_enabled", False))
                else "HISTORICAL_BUSINESS_COMPATIBILITY"
            ),
        })
    if division and row.get("zone_division") == division:
        reasons.append({"kind": "preferred_division", "value": division})
    if pd.notna(row.get("distance_km")):
        reasons.append({
            "kind": "working_location_distance",
            "value": round(float(row["distance_km"]), 2),
            "unit": "km",
        })
    if profile:
        selected = [
            name for field, name in (
                ("market_preference", "commercial"),
                ("transport_preference", "access"),
                ("parking_preference", "facilities"),
            )
            if bool(profile.get(field))
        ]
        priority = str(profile.get("priority_profile") or "BALANCED")
        if priority != "BALANCED" or selected:
            reasons.append({
                "kind": "vendor_priorities",
                "value": priority,
                "selected": selected,
            })
        if row.get("requirement_data_source") == REQUIREMENT_SOURCE:
            reasons.append({
                "kind": "requirements_fit",
                "exact_match": bool(row.get("requirement_exact_match", False)),
                "matched": int(row.get("requirement_match_count", 0)),
                "total": int(row.get("requirement_constraint_count", 0)),
            })
            reasons.extend([
                {
                    "kind": "operating_period_match",
                    "requested": profile.get("preferred_operating_period"),
                    "allowed": row.get("allowed_operating_periods"),
                    "score": row.get("operating_period_match_score"),
                    "synthetic": True,
                },
                {
                    "kind": "space_match",
                    "requested": profile.get("required_space_sqm"),
                    "available": row.get("available_stall_space_sqm"),
                    "score": row.get("space_match_score"),
                    "synthetic": True,
                },
                {
                    "kind": "budget_match",
                    "requested": profile.get("max_monthly_budget"),
                    "monthly_fee": row.get("monthly_fee"),
                    "score": row.get("budget_match_score"),
                    "synthetic": True,
                },
            ])
    available = row.get("available_capacity")
    if pd.notna(available):
        reasons.append({"kind": "live_availability", "value": int(available)})
    return reasons


def _requirement_coverage(profile):
    """Disclose which saved inputs can currently affect ranking."""
    if not profile:
        return []
    active = requirement_ranking_enabled()
    coverage = []
    for name, reason in (
        ("preferred_operating_period", "REVIEWED_ZONE_OPERATING_HOURS_UNAVAILABLE"),
        ("required_space_sqm", "REVIEWED_ZONE_USABLE_SPACE_UNAVAILABLE"),
        ("max_monthly_budget", "REVIEWED_ZONE_COST_DATA_UNAVAILABLE"),
    ):
        value = profile.get(name)
        coverage.append({
            "input": name,
            "value": value,
            "status": "SYNTHETIC_DEMO_EVALUATED" if active and value is not None else "NOT_PROVIDED" if value is None else "NOT_EVALUATED",
            "reason": REQUIREMENT_SOURCE if active and value is not None else "VENDOR_INPUT_NOT_PROVIDED" if value is None else reason,
        })
    return coverage


@router.get("/api/recommendations/{zone_id}/ai-explanation")
def recommendation_ai_explanation(zone_id: str, request: FastAPIRequest):
    """Explain one current eligible result for the signed-in vendor.

    Scores and evidence are recomputed server-side.  The client cannot submit
    factor values or ask for another vendor's recommendation context.
    """
    session = request_session(request, "VENDOR")
    vendor_id = session.get("vendor_id")
    profile = get_vendor_profile(vendor_id, database_path=dependencies.DATABASE_PATH)
    if profile is None:
        raise HTTPException(404, "Vendor profile not found")
    active = get_active_allocation_for_vendor(vendor_id, dependencies.DATABASE_PATH)
    exclude_zone = str(active["zone_id"]) if active is not None else ""
    payload = Request(vendor_id=vendor_id, exclude_zone=exclude_zone, top_n=20)
    context = resolve_recommendation_context(payload, request, use_saved_vendor_preferences=True)
    try:
        result = recommend(
            context["business"],
            context["division"],
            context["engine_vendor_id"],
            20,
            exclude_zone,
            False,
            use_live_status=True,
            database_path=dependencies.DATABASE_PATH,
            factor_weights=context["weight_profile"]["final_weights"],
            include_all=True,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    candidates = result.attrs.get("all_candidates", result)
    matching = candidates.loc[
        candidates["zone_id"].astype(str).eq(str(zone_id)) & candidates["score"].notna()
    ]
    if matching.empty:
        raise HTTPException(404, "Zone is not a current eligible recommendation for this vendor")
    row = matching.iloc[0]
    effective_weights = result.attrs.get(
        "effective_factor_weights", context["weight_profile"]["final_weights"]
    )
    factors = explain(row, effective_weights)
    live_evidence = active_vendor_category_counts(
        context["business"], dependencies.DATABASE_PATH
    ).get(str(zone_id), {})
    capacity_evidence = zone_capacity_analysis(dependencies.DATABASE_PATH).get(str(zone_id), {})
    business_factor = next((factor for factor in factors if factor["key"] == "business"), None)
    if business_factor is not None:
        business_factor["evidence"] = [
            {"label": "Current same-category vendors", "value": live_evidence.get("current_same_category_vendors", 0)},
            {"label": "Historical same-category records", "value": row.get("same_business_count") or 0},
            {"label": "Historical text-associated records", "value": row.get("evidence_count") or 0},
            {"label": "Accepted historical associations", "value": capacity_evidence.get("accepted_historical_association_count", 0)},
        ]
    response = generate_explanations(
        zone_id=str(zone_id),
        factors=factors,
        profile=profile,
        requester_scope=f"vendor:{vendor_id}",
    )
    return clean({
        **response,
        "zone_id": str(zone_id),
        "factor_order": list(FACTOR_ORDER),
        "scores_unchanged": True,
    })

@router.post(
    "/api/recommendations"
)
def recommendations(
    req: Request,
    request: FastAPIRequest,
):

    context = (
        resolve_recommendation_context(
            req,
            request,
            use_saved_vendor_preferences=True,
        )
    )


    business = context[
        "business"
    ]


    division = context[
        "division"
    ]


    engine_vendor_id = context[
        "engine_vendor_id"
    ]


    profile = context[
        "profile"
    ]


    weight_profile = context[
        "weight_profile"
    ]


    effective_weights = (
        weight_profile[
            "final_weights"
        ]
    )

    exclude_zone = req.exclude_zone
    location = None
    radius_km = None
    saved_radius = None
    location_policy = None
    if context["vendor_session"]:
        active = get_active_allocation_for_vendor(profile["vendor_id"], dependencies.DATABASE_PATH)
        if active is not None:
            exclude_zone = active["zone_id"]

    try:
        if context["vendor_session"]:
            location_policy = configured_location_policy()
            if location_policy is not None:
                location = saved_working_location(profile)
            saved_radius = profile.get("preferred_radius_km")
            if location is not None and saved_radius in DISTANCE_RADII_KM and not req.expand_search:
                radius_km = saved_radius

        result = recommend(
            business,
            division,
            engine_vendor_id,
            req.top_n,
            exclude_zone,
            req.require_verified,
            use_live_status=True,
            database_path=dependencies.DATABASE_PATH,
            factor_weights=(
                effective_weights
            ),
            include_all=True,
            location=location,
            radius_km=radius_km,
            location_policy=location_policy,
            vendor_requirements=profile,
        )


    except ValueError as exc:

        raise HTTPException(
            422,
            str(
                exc
            ),
        ) from exc

    # The engine removes the division factor after enforcing an explicit
    # division as a hard candidate constraint.  Use those actual weights in
    # explanations and response metadata so the API remains transparent.
    effective_weights = result.attrs.get(
        "effective_factor_weights",
        effective_weights,
    )


    metadata = {
        "candidate_count_before_live_filter":
            result.attrs.get(
                "candidate_count_before_live_filter",
                0,
            ),

        "candidate_count_after_live_filter":
            result.attrs.get(
                "candidate_count_after_live_filter",
                0,
            ),

        "candidate_count_after_verified_filter":
            result.attrs.get(
                "candidate_count_after_verified_filter",
                0,
            ),

        "live_filter_applied":
            result.attrs.get(
                "live_filter_applied",
                True,
            ),

        "personalization_applied":
            bool(
                profile
            ),

        "priority_profile":
            (
                profile[
                    "priority_profile"
                ]

                if profile

                else "BALANCED"
            ),

        "preference_flags": {
            "parking":
                bool(
                    profile
                    and profile[
                        "parking_preference"
                    ]
                ),

            "transport":
                bool(
                    profile
                    and profile[
                        "transport_preference"
                    ]
                ),

            "market":
                bool(
                    profile
                    and profile[
                        "market_preference"
                    ]
                ),
        },

        "weight_source":
            weight_profile[
                "weight_source"
            ],

        "ahp_consistency_ratio":
            weight_profile[
                "ahp_consistency_ratio"
            ],

        "base_factor_weights":
            weight_profile[
                "base_weights"
            ],

        "effective_factor_weights":
            effective_weights,

        "strict_division_filter_applied":
            result.attrs.get(
                "strict_division_filter_applied",
                False,
            ),

        "selected_division":
            division or None,

        "candidate_count_before_division_filter":
            result.attrs.get(
                "candidate_count_before_division_filter",
                0,
            ),

        "candidate_count_after_division_filter":
            result.attrs.get(
                "candidate_count_after_division_filter",
                0,
            ),

        "division_weight_handling":
            result.attrs.get(
                "division_weight_handling",
            ),

        "weight_modifiers":
            weight_profile[
                "multipliers"
            ],
        "requirement_coverage": _requirement_coverage(profile),
    }

    if result.attrs.get("business_aware_mcda_experiment_enabled", False):
        metadata.update({
            "business_aware_mcda_experiment_enabled": True,
            "business_aware_mcda_policy_version": result.attrs.get(
                "business_aware_mcda_policy_version"
            ),
        })

    metadata["location_ranking"] = {
        "enabled": location_policy is not None,
        "applied": location is not None,
        "radius_km": radius_km,
        "expanded": bool(location is not None and req.expand_search and saved_radius in DISTANCE_RADII_KM),
        "can_expand": radius_km is not None and len(result) < req.top_n,
    }
    if location is not None:
        metadata["location_ranking"].update({
            "proximity_weight": location_policy.proximity_weight,
            "decay_km": location_policy.decay_km,
        })

    all_candidates = result.attrs["all_candidates"]
    ranks = {zone_id:index+1 for index,zone_id in enumerate(all_candidates.loc[all_candidates.score.notna(), "zone_id"])}
    def record(row):
        item = {key:row.get(key) for key in fields}
        item.update({"title":row.zone_id, "description":row.get("official_description"),
                     "rank":ranks.get(row.zone_id),
                     "location_source":row.get("reference_location_source"),
                     "scoreability_reason":row.get("scoreability_reason"),
                     "factors":explain(row, effective_weights)})
        item.update(_ranking_reason(row))
        return clean(item)

    # One score calculation supplies both the highlighted and complete lists.
    # These additions retain the existing recommendations/count response contract.
    fields = list(all_candidates.columns)
    remaining = all_candidates.loc[all_candidates.score.notna() & ~all_candidates.zone_id.isin(result.zone_id)]
    unscorable = all_candidates.loc[all_candidates.score.isna()]
    live = get_live_zone_status_map(dependencies.DATABASE_PATH)
    official = pd.read_csv(dataset_path("official_zones"), keep_default_na=False)
    eligible_ids = set(all_candidates.zone_id)
    ineligible = []
    for zone in official.itertuples(index=False):
        if zone.zone_id == exclude_zone:
            reason = "CURRENT_ZONE_EXCLUDED"
        elif zone.zone_id in eligible_ids:
            continue
        elif division and zone.division != division:
            reason = "OUTSIDE_PREFERRED_DIVISION"
        else:
            reason = zone_ineligibility_reason(zone.zone_type, live.get(zone.zone_id)) or "AVAILABILITY_NOT_RECENTLY_VERIFIED"
        ineligible.append({"zone_id":zone.zone_id, "title":zone.zone_id, "description":zone.official_description,
                           "division":zone.division, "zone_type":zone.zone_type, "reason":reason})
    metadata.update({"remaining_recommendations":[record(row) for _,row in remaining.iterrows()],
                     "eligible_unscorable_zones":[record(row) for _,row in unscorable.iterrows()],
                     "ineligible_zones":ineligible, "eligible_scoreable_count":int(all_candidates.score.notna().sum()),
                     "eligible_unscorable_count":len(unscorable), "official_free_zone_count":int(official.zone_type.eq("FREE").sum()),
                     "model_version":CATALOG.get("active_model_version"),
                     "locality_scoring":{"applied":False, "reason":"REVIEWED_LOCALITY_REFERENCE_UNAVAILABLE" if profile and profile.get("preferred_locality") else "NO_LOCALITY_PREFERENCE"}})
    if result.empty:

        return {
            "recommendations":
                [],

            "count":
                0,

            "mode":
                "research",

            "notice":
                (
                    "No scorable eligible zones were found within the selected distance."
                    if radius_km is not None
                    else f"No suitable available zones were found in the selected division: {division}. No allocation is inferred."
                    if division
                    else
                    "No operationally available zones meet the selected "
                    "filters. No allocation is inferred."
                ),

            **metadata,
        }


    fields = [
        "rank",
        "zone_id",
        "zone_division",
        "official_description",
        "official_capacity",
        "score",
        "score_type",
        "candidate_status",
        "fallback_used",
        "reference_group_id",
        "shared_reference",
        "shared_reference_group_size",
        "reference_warning",
        "geometry_method",
        "source_confidence",
        "environment_cluster",
        "evidence_count",
        "same_business_count",
        "score_coverage",
        "limitations",
        "reason",
        "verified_available_capacity",
        "verified_at",
        "live_verified",
        "evidence_method",
        "distance_to_major_road_m",
        "distance_to_bus_access_m",
        "pedestrian_road_density_250m_per_km2",
        "commercial_poi_count_250m",
        "market_poi_count_500m",
        "food_poi_count_250m",
        "healthcare_count_500m",
        "education_count_500m",
        "toilet_count_500m",
        "parking_count_500m",
        "live_status",
        "current_vendor_count",
        "available_capacity",
        "reference_location_source",
        *PERSONALIZED_FIELDS,
    ]


    active_category_counts = active_vendor_category_counts(
        business,
        dependencies.DATABASE_PATH,
    )
    capacity_by_zone = zone_capacity_analysis(dependencies.DATABASE_PATH)
    scoreable_candidates = all_candidates.loc[all_candidates.score.notna()].copy()
    comparative_ranks = {}
    for factor in FACTOR_ORDER:
        column = f"{factor}_score"
        if column in scoreable_candidates:
            comparative_ranks[factor] = scoreable_candidates.set_index("zone_id")[column].rank(
                method="min", ascending=False, na_option="bottom"
            ).to_dict()
    comparative_count = len(scoreable_candidates)
    records = []


    for _, row in (
        result.iterrows()
    ):

        item = {
            key:
                row.get(
                    key
                )

            for key
            in fields
        }


        item[
            "factors"
        ] = explain(
            row,
            effective_weights,
        )
        for factor in item["factors"]:
            rank = comparative_ranks.get(factor.get("key"), {}).get(str(row.get("zone_id")))
            factor["candidate_rank"] = int(rank) if pd.notna(rank) else None
            factor["candidate_count"] = comparative_count
        live_evidence = active_category_counts.get(str(row.get("zone_id")), {})
        capacity_evidence = capacity_by_zone.get(str(row.get("zone_id")), {})
        item.update({
            "current_total_vendors": live_evidence.get("current_total_vendors", 0),
            "current_same_category_vendors": live_evidence.get("current_same_category_vendors", 0),
            "historical_same_category_records": row.get("same_business_count"),
            "historical_text_association_records": row.get("evidence_count"),
            "historical_vendor_zone_associations": row.get("evidence_count"),
            "accepted_historical_association_count": capacity_evidence.get(
                "accepted_historical_association_count", 0
            ),
        })
        if item["factors"]:
            business_factor = next(
                (factor for factor in item["factors"] if factor.get("key") == "business"),
                None,
            )
            if business_factor is not None:
                business_factor["evidence"] = [
                    {"label": "Current same-category vendors", "value": item["current_same_category_vendors"]},
                    {"label": "Historical same-category records", "value": item["historical_same_category_records"] or 0},
                    {"label": "Historical text-associated records", "value": item["historical_text_association_records"] or 0},
                    {"label": "Accepted historical associations", "value": item["accepted_historical_association_count"]},
                ]
        item.update({"title":row.zone_id, "description":row.get("official_description"), "location_source":row.get("reference_location_source"),
                     "why_recommended": _why_recommended(row, profile, business, division)})
        item.update(_ranking_reason(row))


        records.append(
            clean(
                item
            )
        )


    return {
        "recommendations":
            records,

        "count":
            len(
                records
            ),

        "mode":
            "research",

        "notice":
            (
                "Explainable decision-support "
                "scores, not success probabilities "
                "or municipal permits."
            ),

        **metadata,
    }

@router.post(
    "/api/recommendations/sensitivity",
    tags=[
        "Research Evaluation"
    ],
)
def recommendation_sensitivity(
    payload: SensitivityRequest,
    request: FastAPIRequest,
):
    """Evaluate ranking sensitivity to reasonable MCDA weight changes."""

    context = (
        resolve_recommendation_context(
            payload,
            request,
        )
    )


    config = SensitivityConfig(
        top_n=(
            payload.top_n
        ),
        monte_carlo_samples=(
            payload
            .monte_carlo_samples
        ),
        monte_carlo_delta=(
            payload
            .monte_carlo_delta
        ),
        random_seed=(
            payload.random_seed
        ),
    )


    try:

        report = (
            evaluate_weight_sensitivity(
                business=(
                    context[
                        "business"
                    ]
                ),
                division=(
                    context[
                        "division"
                    ]
                ),
                vendor_id=(
                    context[
                        "engine_vendor_id"
                    ]
                ),
                exclude_zone=(
                    payload.exclude_zone
                ),
                vendor_profile=(
                    context[
                        "profile"
                    ]
                ),
                require_verified=(
                    payload.require_verified
                ),
                use_live_status=True,
                database_path=(
                    dependencies.DATABASE_PATH
                ),
                config=config,
            )
        )


    except ValueError as exc:

        raise HTTPException(
            422,
            str(
                exc
            ),
        ) from exc


    response = {
        key:
            value

        for (
            key,
            value,
        ) in report.items()

        if key not in {
            "scenario_metrics",
            "scenario_top_k",
        }
    }


    response[
        "requested_vendor_id"
    ] = (
        payload.vendor_id
        or None
    )


    if payload.include_scenarios:

        response[
            "scenario_metrics"
        ] = (
            report[
                "scenario_metrics"
            ]
            .to_dict(
                orient="records"
            )
        )


        response[
            "scenario_top_k"
        ] = (
            report[
                "scenario_top_k"
            ]
            .to_dict(
                orient="records"
            )
        )


    return clean(
        response
    )
