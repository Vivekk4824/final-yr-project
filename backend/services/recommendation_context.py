"""Resolve saved and explicit recommendation preferences."""
from fastapi import HTTPException, Request

from backend.core import context as dependencies
from backend.core.security import require_vendor_owner
from backend.recommendation.decision_policy import derive_mcda_weights
from backend.services.vendors import get_vendor_profile


def resolve_recommendation_context(
    payload,
    request: Request,
    *,
    use_saved_vendor_preferences: bool = False,
):
    business = payload.business
    division = payload.division
    vendor_id = payload.vendor_id
    session = None
    if vendor_id:
        session = require_vendor_owner(request, vendor_id, allow_admin=True)
    elif use_saved_vendor_preferences and not dependencies.AUTH_TEST_BYPASS:
        token = request.cookies.get(dependencies.SESSION_COOKIE_NAME)
        if token:
            session = dependencies.get_session(token, database_path=dependencies.DATABASE_PATH)
            if session and session["role"] == "VENDOR":
                vendor_id = session["vendor_id"]

    vendor_session = bool(session and session["role"] == "VENDOR")
    profile = None
    engine_vendor_id = vendor_id
    if vendor_id:
        profile = get_vendor_profile(vendor_id, database_path=dependencies.DATABASE_PATH)
        if profile is None:
            raise HTTPException(404, f"Unknown vendor_id: {vendor_id}")
        saved = use_saved_vendor_preferences and vendor_session
        if saved or not business:
            business = profile["business_category"]
        if saved or not division:
            division = profile["preferred_division"] or ""
        if profile["vendor_type"] == "NEW":
            engine_vendor_id = ""

    try:
        weight_profile = derive_mcda_weights(profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "business": business,
        "division": division,
        "engine_vendor_id": engine_vendor_id,
        "vendor_session": vendor_session,
        "profile": profile,
        "weight_profile": weight_profile,
    }
