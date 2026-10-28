"""Recommendations HTTP endpoints; existing contracts retained."""
from __future__ import annotations
from backend.core import context as dependencies
from fastapi import Request as FastAPIRequest
from fastapi import HTTPException
from backend.schemas.api import Request
from backend.recommendation_evaluation import SensitivityConfig
from backend.schemas.api import SensitivityRequest
from backend.core.serialization import clean
from backend.recommendation_evaluation import evaluate_weight_sensitivity
from backend.services.explanations import explain
from backend.mcda_engine import recommend
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
from backend.decision_policy import FACTOR_ORDER
from backend.services.capacity_analysis import zone_capacity_analysis
from fastapi import APIRouter
router = APIRouter()


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
    context = resolve_recommendation_context(payload, request)
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


    try:

        result = recommend(
            business,
            division,
            engine_vendor_id,
            req.top_n,
            req.exclude_zone,
            req.require_verified,
            use_live_status=True,
            database_path=dependencies.DATABASE_PATH,
            factor_weights=(
                effective_weights
            ),
            include_all=True,
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
                req.vendor_id
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
    }

    if result.attrs.get("business_aware_mcda_experiment_enabled", False):
        metadata.update({
            "business_aware_mcda_experiment_enabled": True,
            "business_aware_mcda_policy_version": result.attrs.get(
                "business_aware_mcda_policy_version"
            ),
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
        if zone.zone_id == req.exclude_zone:
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
                    "No suitable available zones were found in the selected "
                    f"division: {division}. No allocation is inferred."
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
    ]


    active_category_counts = active_vendor_category_counts(
        business,
        dependencies.DATABASE_PATH,
    )
    capacity_by_zone = zone_capacity_analysis(dependencies.DATABASE_PATH)
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
        item.update({"title":row.zone_id, "description":row.get("official_description"), "location_source":row.get("reference_location_source")})


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
