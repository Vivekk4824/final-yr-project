"""Extracted services responses helpers; behavior retained."""
from __future__ import annotations
from backend.core import context as dependencies
from backend.schemas.response_fields import ALLOCATION_REQUEST_RESPONSE_FIELDS
from backend.schemas.response_fields import ALLOCATION_RESPONSE_FIELDS
from backend.services.vendors import get_vendor_profile
from backend.services.vendors import get_vendor_profiles

def allocation_request_response(
    row,
):
    """Add safe vendor context to an allocation-request row."""

    response = {
        field:
            row[
                field
            ]

        for field
        in ALLOCATION_REQUEST_RESPONSE_FIELDS
    }


    profile = get_vendor_profile(
        row[
            "vendor_id"
        ],
        database_path=dependencies.DATABASE_PATH,
    )


    response[
        "vendor_name"
    ] = (
        profile.get(
            "full_name"
        )
        if profile
        else None
    )


    response[
        "business_name"
    ] = (
        profile.get(
            "business_name"
        )
        if profile
        else None
    )


    response[
        "application_vendor_id"
    ] = (
        profile.get(
            "application_vendor_id"
        )
        if profile
        else None
    )


    response[
        "vendor_type"
    ] = (
        profile.get(
            "vendor_type"
        )
        if profile
        else None
    )


    return response

def allocation_response(
    row,
):
    """Add safe vendor context to an allocation row."""

    response = {
        field:
            row[
                field
            ]

        for field
        in ALLOCATION_RESPONSE_FIELDS
    }


    profile = get_vendor_profile(
        row[
            "vendor_id"
        ],
        database_path=dependencies.DATABASE_PATH,
    )


    response[
        "application_vendor_id"
    ] = (
        profile.get(
            "application_vendor_id"
        )
        if profile
        else None
    )


    response[
        "vendor_name"
    ] = (
        profile.get(
            "full_name"
        )
        if profile
        else None
    )


    response[
        "vendor_type"
    ] = (
        profile.get(
            "vendor_type"
        )
        if profile
        else None
    )


    return response


def allocation_responses(
    rows,
):
    """Project an allocation list while resolving vendor profiles in a batch."""
    profiles = get_vendor_profiles(
        [row["vendor_id"] for row in rows],
        database_path=dependencies.DATABASE_PATH,
    )
    responses = []
    for row in rows:
        response = {
            field: row[field]
            for field in ALLOCATION_RESPONSE_FIELDS
        }
        profile = profiles.get(row["vendor_id"])
        response["application_vendor_id"] = (
            profile.get("application_vendor_id") if profile else None
        )
        response["vendor_name"] = profile.get("full_name") if profile else None
        response["vendor_type"] = profile.get("vendor_type") if profile else None
        responses.append(response)
    return responses
