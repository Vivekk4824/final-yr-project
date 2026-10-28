"""Unified vendor profiles across operational and historical data.

Historical recommendation data is non-PII and always required.

The optional historical identity CSV may contain privacy-restricted fields
such as vendor names. The application must continue functioning when that
private source is not deployed.

No plaintext phone numbers or authentication credentials are exposed from
this module.
"""

from __future__ import annotations
from backend.core.data_paths import dataset_path

import base64
import binascii
import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.repositories.database import DATABASE_PATH, PREFERRED_LANGUAGES, PRIORITY_PROFILES, OperationalNotFoundError, OperationalValidationError, connect, create_operational_vendor, get_operational_vendor, save_operational_vendor_profile
from backend.mcda_engine import CATEGORIES, DATA


# ---------------------------------------------------------------------------
# Source files
# ---------------------------------------------------------------------------

HISTORICAL_VENDOR_PATH = (
    DATA
    / "vendor_training_registry.csv"
)

# Optional privacy-restricted source.
#
# This file is intentionally allowed to be absent in Git/deployment builds.
HISTORICAL_IDENTITY_PATH = dataset_path("historical_vendors")

CANDIDATE_ZONE_PATH = (
    DATA
    / "candidate_zone_snapshot.csv"
)


@lru_cache(maxsize=4)
def _official_zone_directory_versioned(
    path: str, modified_ns: int, size: int,
) -> dict[str, dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        return {row["zone_id"]: row for row in csv.DictReader(source)}


def _official_zone_directory() -> dict[str, dict[str, str]]:
    path = Path(dataset_path("official_zones")).resolve()
    stat = path.stat()
    return _official_zone_directory_versioned(str(path), stat.st_mtime_ns, stat.st_size)


EDITABLE_PROFILE_FIELDS = {
    "full_name",
    "business_name",
    "business_category",
    "preferred_division",
    "preferred_locality",
    "priority_profile",
    "parking_preference",
    "transport_preference",
    "market_preference",
    "preferred_language",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _optional_text(
    value: Any,
) -> str | None:
    """Normalize optional text without inventing values."""

    if value is None:
        return None

    text = str(value).strip()

    return text or None


# ---------------------------------------------------------------------------
# Historical source loading
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _historical_identity_map(
    path: str = str(
        HISTORICAL_IDENTITY_PATH
    ),
) -> dict[
    str,
    dict[
        str,
        str | None,
    ],
]:
    """Load the optional historical identity overlay.

    The privacy-restricted source is deliberately optional.

    If it is not deployed, recommendation, allocation and authentication
    workflows must continue using the non-PII vendor registry.

    If the source *is* present but malformed, fail explicitly because silently
    accepting corrupted identity information would be unsafe.
    """

    source_path = Path(
        path
    )


    if not source_path.exists():
        return {}


    if not source_path.is_file():

        raise OperationalValidationError(
            "Historical identity source "
            "exists but is not a file"
        )


    with source_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as source:

        reader = csv.DictReader(
            source
        )


        fieldnames = set(
            reader.fieldnames
            or []
        )


        if (
            "vendor_id"
            not in fieldnames
        ):

            raise OperationalValidationError(
                "Historical identity source "
                "is missing vendor_id"
            )


        identities: dict[
            str,
            dict[
                str,
                str | None,
            ],
        ] = {}


        for row in reader:

            vendor_id = (
                row.get(
                    "vendor_id"
                )
                or ""
            ).strip()


            if not vendor_id:
                continue


            identities[
                vendor_id
            ] = {

                "full_name":
                    _optional_text(
                        row.get(
                            "vendor_name_english"
                        )
                    ),

                # Historical source contains business type,
                # but does not provide a distinct business/stall name.
                "business_name":
                    None,
                "source_division": _optional_text(row.get("division")),
            }


        return identities


@lru_cache(maxsize=4)
def _historical_vendor_map(
    path: str = str(
        HISTORICAL_VENDOR_PATH
    ),
) -> dict[
    str,
    dict[
        str,
        str | None,
    ],
]:
    """Load the non-PII historical recommendation registry."""

    source_path = Path(
        path
    )


    if not source_path.exists():

        raise OperationalValidationError(
            "Historical vendor registry "
            f"is unavailable: {source_path}"
        )


    with source_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as source:

        reader = csv.DictReader(
            source
        )


        fieldnames = set(
            reader.fieldnames
            or []
        )


        required = {
            "vendor_id",
            "business_category",
            "vendor_division",
        }


        missing = (
            required
            - fieldnames
        )


        if missing:

            raise OperationalValidationError(
                "Historical vendor registry "
                "is missing columns: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )


        vendors: dict[
            str,
            dict[
                str,
                str | None,
            ],
        ] = {}


        for row in reader:

            vendor_id = (
                row.get(
                    "vendor_id"
                )
                or ""
            ).strip()


            if not vendor_id:
                continue


            category = (
                row.get(
                    "business_category"
                )
                or ""
            ).strip()


            division = _optional_text(
                row.get(
                    "vendor_division"
                )
            )


            vendors[
                vendor_id
            ] = {

                "business_category":
                    category,

                "preferred_division":
                    division,
            }


        return vendors


@lru_cache(maxsize=4)
def valid_divisions(
    path: str = str(
        CANDIDATE_ZONE_PATH
    ),
) -> frozenset[str]:
    """Return currently supported municipal divisions."""

    source_path = Path(
        path
    )


    if not source_path.exists():

        raise OperationalValidationError(
            "Candidate-zone snapshot "
            f"is unavailable: {source_path}"
        )


    with source_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as source:

        reader = csv.DictReader(
            source
        )


        fieldnames = set(
            reader.fieldnames
            or []
        )


        if (
            "zone_division"
            not in fieldnames
        ):

            raise OperationalValidationError(
                "Candidate-zone snapshot "
                "is missing zone_division"
            )


        return frozenset(

            division

            for row in reader

            if (
                division := _optional_text(
                    row.get(
                        "zone_division"
                    )
                )
            )

            and division
            != "Citywide"
        )


# ---------------------------------------------------------------------------
# Profile normalization
# ---------------------------------------------------------------------------


def _normalize_operational(
    row,
) -> dict[
    str,
    Any,
]:
    """Convert an operational SQLite row into the public profile contract."""

    return {

        "vendor_id":
            row[
                "vendor_id"
            ],

        "application_vendor_id":
            row[
                "application_vendor_id"
            ],

        "vendor_type":
            row[
                "vendor_type"
            ],

        "full_name":
            row[
                "full_name"
            ],

        "business_name":
            row[
                "business_name"
            ],

        "business_category":
            row[
                "business_category"
            ],

        "preferred_division":
            row[
                "preferred_division"
            ],

        "preferred_locality":
            row[
                "preferred_locality"
            ],

        "priority_profile":
            row[
                "priority_profile"
            ],

        "parking_preference":
            bool(
                row[
                    "parking_preference"
                ]
            ),

        "transport_preference":
            bool(
                row[
                    "transport_preference"
                ]
            ),

        "market_preference":
            bool(
                row[
                    "market_preference"
                ]
            ),

        "preferred_language":
            row[
                "preferred_language"
            ],

        "status":
            row[
                "status"
            ],

        "created_at":
            row[
                "created_at"
            ],

        "updated_at":
            row[
                "updated_at"
            ],
    }


def _historical_profile(
    vendor_id: str,
    historical_path: str | Path,
    identity_path: str | Path = (
        HISTORICAL_IDENTITY_PATH
    ),
) -> dict[
    str,
    Any,
] | None:
    """Build a historical vendor profile.

    Non-PII business/division information comes from the model registry.

    Name information is overlaid only when the optional private identity source
    is available.
    """

    source = (
        _historical_vendor_map(

            str(
                Path(
                    historical_path
                ).resolve()
            )

        ).get(
            vendor_id
        )
    )


    if source is None:
        return None


    identity = (
        _historical_identity_map(

            str(
                Path(
                    identity_path
                ).resolve()
            )

        ).get(
            vendor_id,
            {},
        )
    )


    return {

        "vendor_id":
            vendor_id,

        "application_vendor_id":
            None,

        "vendor_type":
            "EXISTING_IMPORTED",

        "full_name":
            identity.get(
                "full_name"
            ),

        "business_name":
            identity.get(
                "business_name"
            ),

        "business_category":
            source[
                "business_category"
            ],

        "preferred_division":
            source[
                "preferred_division"
            ],

        "preferred_locality":
            None,

        "priority_profile":
            "BALANCED",

        "parking_preference":
            False,

        "transport_preference":
            False,

        "market_preference":
            False,

        "preferred_language":
            "en",

        "status":
            "ACTIVE",

        "created_at":
            None,

        "updated_at":
            None,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_vendor_profile(
    values: dict[
        str,
        Any,
    ],
    *,
    partial: bool = False,
) -> None:
    """Validate mutable operational profile fields."""

    for field, maximum in (
        (
            "full_name",
            120,
        ),
        (
            "business_name",
            120,
        ),
    ):

        if (
            field in values
            and values[
                field
            ]
            is not None
        ):

            value = (

                values[
                    field
                ].strip()

                if isinstance(
                    values[
                        field
                    ],
                    str,
                )

                else ""
            )


            if not value:

                raise OperationalValidationError(
                    f"{field} must not be empty"
                )


            if (
                len(
                    value
                )
                > maximum
            ):

                raise OperationalValidationError(
                    f"{field} must be at most "
                    f"{maximum} characters"
                )


            values[
                field
            ] = value


    if (
        not partial
        or "business_category"
        in values
    ):

        category = (
            values.get(
                "business_category"
            )
        )


        if (
            category
            not in CATEGORIES
        ):

            raise OperationalValidationError(
                "business_category must be one of: "
                + ", ".join(
                    CATEGORIES
                )
            )


    if (
        "preferred_division"
        in values

        and values[
            "preferred_division"
        ]
        is not None
    ):

        if (
            values[
                "preferred_division"
            ]
            not in valid_divisions()
        ):

            raise OperationalValidationError(
                "Unknown preferred_division"
            )


    if (

        "priority_profile"
        in values

        and values[
            "priority_profile"
        ]
        not in PRIORITY_PROFILES
    ):

        raise OperationalValidationError(
            "priority_profile must be one of: "
            + ", ".join(
                PRIORITY_PROFILES
            )
        )


    if (

        "preferred_language"
        in values

        and values[
            "preferred_language"
        ]
        not in PREFERRED_LANGUAGES
    ):

        raise OperationalValidationError(
            "preferred_language must be one of: "
            + ", ".join(
                PREFERRED_LANGUAGES
            )
        )


    for field in (
        "parking_preference",
        "transport_preference",
        "market_preference",
    ):

        if (

            field in values

            and not isinstance(
                values[
                    field
                ],
                bool,
            )
        ):

            raise OperationalValidationError(
                f"{field} must be a boolean"
            )


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def get_vendor_profile(
    vendor_id: str,
    database_path: str | Path = (
        DATABASE_PATH
    ),
    historical_path: str | Path = (
        HISTORICAL_VENDOR_PATH
    ),
    identity_path: str | Path = (
        HISTORICAL_IDENTITY_PATH
    ),
) -> dict[
    str,
    Any,
] | None:
    """Resolve operational vendor first, then historical source."""

    operational = (
        get_operational_vendor(
            vendor_id,
            database_path,
        )
    )


    if (
        operational
        is not None
    ):

        return (
            _normalize_operational(
                operational
            )
        )


    return _historical_profile(

        vendor_id,

        historical_path,

        identity_path,
    )


def get_vendor_profiles(
    vendor_ids: list[str],
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, dict[str, Any]]:
    """Resolve many vendor profiles with one operational database read."""
    unique_ids = list(dict.fromkeys(vendor_ids))
    if not unique_ids:
        return {}

    profiles: dict[str, dict[str, Any]] = {}
    connection = connect(database_path)
    try:
        for start in range(0, len(unique_ids), 500):
            batch = unique_ids[start:start + 500]
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"SELECT * FROM operational_vendors WHERE vendor_id IN ({placeholders})",
                tuple(batch),
            ).fetchall()
            profiles.update({
                row["vendor_id"]: _normalize_operational(row)
                for row in rows
            })
    finally:
        connection.close()

    for vendor_id in unique_ids:
        if vendor_id not in profiles:
            profile = _historical_profile(
                vendor_id,
                HISTORICAL_VENDOR_PATH,
                HISTORICAL_IDENTITY_PATH,
            )
            if profile is not None:
                profiles[vendor_id] = profile
    return profiles


def register_vendor(
    values: dict[
        str,
        Any,
    ],
    database_path: str | Path = (
        DATABASE_PATH
    ),
) -> dict[
    str,
    Any,
]:
    """Register a new operational vendor."""

    validate_vendor_profile(
        values
    )


    return _normalize_operational(

        create_operational_vendor(
            values,
            database_path,
        )
    )


def update_vendor_profile(
    vendor_id: str,
    updates: dict[
        str,
        Any,
    ],
    database_path: str | Path = (
        DATABASE_PATH
    ),
    historical_path: str | Path = (
        HISTORICAL_VENDOR_PATH
    ),
    identity_path: str | Path = (
        HISTORICAL_IDENTITY_PATH
    ),
) -> dict[
    str,
    Any,
]:
    """Create/update the operational overlay for a vendor profile."""

    if not updates:

        raise OperationalValidationError(
            "At least one preference field "
            "must be supplied"
        )


    unknown = (
        set(
            updates
        )
        - EDITABLE_PROFILE_FIELDS
    )


    if unknown:

        raise OperationalValidationError(
            "Fields cannot be updated: "
            + ", ".join(
                sorted(
                    unknown
                )
            )
        )


    validate_vendor_profile(
        updates,
        partial=True,
    )


    current = get_vendor_profile(

        vendor_id,

        database_path,

        historical_path,

        identity_path,
    )


    if current is None:

        raise OperationalNotFoundError(
            f"Unknown vendor_id: {vendor_id}"
        )


    merged = {
        **current,
        **updates,
    }


    row = (
        save_operational_vendor_profile(

            vendor_id,

            current[
                "vendor_type"
            ],

            merged,

            database_path,
        )
    )


    return _normalize_operational(
        row
    )


# ---------------------------------------------------------------------------
# Test / maintenance support
# ---------------------------------------------------------------------------


def clear_vendor_service_caches() -> None:
    """Clear immutable-source caches.

    Useful after explicitly mounting/replacing research source files during
    development or controlled test setup.
    """

    _historical_identity_map.cache_clear()

    _historical_vendor_map.cache_clear()

    valid_divisions.cache_clear()

def list_admin_vendors(*, q="", business_category="", division="", zone_id="", mapping_status="",
                       page=1, page_size=25, database_path=DATABASE_PATH):
    """Return one directory page and hydrate dynamic state only for that page.

    Static CSV registries remain cached and authoritative. PostgreSQL is used
    for filters and the final page rather than transferring all association,
    identity and allocation rows for every request.
    """
    from backend.repositories.database import connect

    historical = _historical_vendor_map(str(Path(HISTORICAL_VENDOR_PATH).resolve()))
    identities = _historical_identity_map(str(Path(HISTORICAL_IDENTITY_PATH).resolve()))
    connection = connect(database_path)
    try:
        operational = {row["vendor_id"]: dict(row) for row in connection.execute(
            "SELECT vendor_id, application_vendor_id, full_name, business_name, business_category, "
            "preferred_division FROM operational_vendors"
        )}
        association_filter_ids = None
        if zone_id or mapping_status:
            clauses, parameters = [], []
            if zone_id:
                clauses.append("matched_zone_id = ? AND ((match_status = 'AUTO_MATCHED' AND "
                               "review_status = 'UNREVIEWED') OR review_status IN ('CONFIRMED','CHANGED'))")
                parameters.append(zone_id)
            if mapping_status:
                clauses.append("match_status = ?")
                parameters.append(mapping_status)
            association_filter_ids = {row["vendor_id"] for row in connection.execute(
                "SELECT vendor_id FROM historical_vendor_zone_associations WHERE " + " AND ".join(clauses),
                tuple(parameters),
            )}

        records = []
        for vendor_id in historical.keys() | operational.keys():
            source = historical.get(vendor_id)
            overlay = operational.get(vendor_id)
            identity = identities.get(vendor_id, {})
            records.append({
                "vendor_id": vendor_id,
                "application_vendor_id": overlay.get("application_vendor_id") if overlay else None,
                "full_name": overlay.get("full_name") if overlay else identity.get("full_name"),
                "business_name": overlay.get("business_name") if overlay else identity.get("business_name"),
                "business_category": overlay.get("business_category") if overlay else source.get("business_category"),
                "source_division": (identity.get("source_division") or source.get("preferred_division")) if source else None,
                "preferred_division": overlay.get("preferred_division") if overlay else source.get("preferred_division"),
                "record_source": "HISTORICAL" if source else "OPERATIONAL",
                "has_profile_overlay": bool(source and overlay),
                "registration_status": "PROFILE_REGISTERED" if overlay else "HISTORICAL_RECORD",
            })
        categories = sorted({row["business_category"] for row in records if row["business_category"]})
        divisions = sorted({row["source_division"] or row["preferred_division"] for row in records if row["source_division"] or row["preferred_division"]})
        query = q.strip().casefold()
        filtered = [row for row in records
                    if (not query or any(query in str(row.get(key) or "").casefold() for key in ("vendor_id", "application_vendor_id", "full_name", "business_name")))
                    and (not business_category or row["business_category"] == business_category)
                    and (not division or (row["source_division"] or row["preferred_division"]) == division)
                    and (association_filter_ids is None or row["vendor_id"] in association_filter_ids)]
        filtered.sort(key=lambda row: (str(row["full_name"] or row["business_name"] or "").casefold(), row["vendor_id"]))
        total = len(filtered)
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, pages)
        page_records = filtered[(page - 1) * page_size:page * page_size]
        page_ids = [row["vendor_id"] for row in page_records]
        dynamic = {}
        if page_ids:
            placeholders = ",".join("?" for _ in page_ids)
            dynamic = {row["vendor_id"]: dict(row) for row in connection.execute(
                f"""WITH identity_state AS (
                         SELECT vendor_id, COUNT(*) AS identity_count,
                                MAX(is_verified) AS verified
                         FROM vendor_auth_identities GROUP BY vendor_id
                       )
                       SELECT ids.vendor_id, h.matched_zone_id, h.match_status,
                              h.review_status, h.candidate_zone_ids_json,
                              h.evidence_types_json, i.identity_count, i.verified,
                              a.allocation_id, a.zone_id AS allocation_zone_id,
                              a.allocated_at, a.allocation_source
                       FROM (SELECT vendor_id FROM historical_vendor_zone_associations
                             UNION SELECT vendor_id FROM operational_vendors) AS ids
                       LEFT JOIN historical_vendor_zone_associations AS h ON h.vendor_id = ids.vendor_id
                       LEFT JOIN identity_state AS i ON i.vendor_id = ids.vendor_id
                       LEFT JOIN allocations AS a ON a.vendor_id = ids.vendor_id AND a.status = 'ACTIVE'
                       WHERE ids.vendor_id IN ({placeholders})""",
                tuple(page_ids),
            )}
        for record in page_records:
            state = dynamic.get(record["vendor_id"], {})
            identity_count = int(state.get("identity_count") or 0)
            record["account_status"] = (
                "PHONE_VERIFIED" if state.get("verified") else
                "UNCLAIMED" if identity_count else "NO_LINKED_IDENTITY"
            )
            record["active_allocation"] = ({
                "allocation_id": state["allocation_id"],
                "vendor_id": record["vendor_id"],
                "zone_id": state["allocation_zone_id"],
                "allocated_at": state["allocated_at"],
                "allocation_source": state["allocation_source"],
            } if state.get("allocation_id") else None)
            if state.get("match_status"):
                review_status = state.get("review_status")
                record["historical_association"] = {
                    "matched_zone_id": state.get("matched_zone_id"),
                    "match_status": state["match_status"],
                    "review_status": review_status,
                    "candidate_zone_ids": json.loads(state.get("candidate_zone_ids_json") or "[]"),
                    "evidence_types": json.loads(state.get("evidence_types_json") or "[]"),
                    "accepted": review_status in {"CONFIRMED", "CHANGED"} or (
                        state["match_status"] == "AUTO_MATCHED" and review_status == "UNREVIEWED"
                    ),
                }
            else:
                record["historical_association"] = None
        accepted_zones = [dict(row) for row in connection.execute(
            """SELECT matched_zone_id AS zone_id, MAX(recorded_division) AS division
               FROM historical_vendor_zone_associations
               WHERE matched_zone_id IS NOT NULL AND
                     ((match_status = 'AUTO_MATCHED' AND review_status = 'UNREVIEWED')
                      OR review_status IN ('CONFIRMED','CHANGED'))
               GROUP BY matched_zone_id ORDER BY matched_zone_id"""
        )]
        official_zones = _official_zone_directory()
        for zone in accepted_zones:
            official = official_zones.get(zone["zone_id"], {})
            zone["division"] = official.get("division") or zone.get("division")
            zone["official_description"] = official.get("official_description")
        return {"vendors": page_records, "total": total, "page": page,
                "page_size": page_size, "pages": pages, "categories": categories,
                "divisions": divisions, "accepted_zones": accepted_zones,
                "mapping_statuses": ["AUTO_MATCHED", "REVIEW_REQUIRED", "UNMATCHED"]}
    finally:
        connection.close()


def admin_vendor_details(vendor_id, database_path=DATABASE_PATH):
    """Read existing vendor relationships without creating identity or allocation state."""
    from backend.repositories.database import connect
    profile = get_vendor_profile(vendor_id, database_path=database_path)
    if profile is None:
        raise OperationalNotFoundError("Vendor profile not found")
    historical = _historical_vendor_map(str(Path(HISTORICAL_VENDOR_PATH).resolve())).get(vendor_id)
    identity = _historical_identity_map(str(Path(HISTORICAL_IDENTITY_PATH).resolve())).get(vendor_id, {})
    connection = connect(database_path)
    try:
        connection.execute("BEGIN")
        operational = connection.execute("SELECT 1 FROM operational_vendors WHERE vendor_id = ?", (vendor_id,)).fetchone()
        account = connection.execute("SELECT COUNT(*) AS total, MAX(is_verified) AS verified FROM vendor_auth_identities WHERE vendor_id = ?", (vendor_id,)).fetchone()
        allocations = [dict(row) for row in connection.execute("SELECT * FROM allocations WHERE vendor_id = ? ORDER BY allocated_at DESC, allocation_id DESC", (vendor_id,))]
        requests = [dict(row) for row in connection.execute("SELECT * FROM allocation_requests WHERE vendor_id = ? ORDER BY created_at DESC, request_id DESC", (vendor_id,))]
        active = next((row for row in allocations if row["status"] == "ACTIVE"), None)
        slot = connection.execute("SELECT zone_id, slot_id, status, width_m, depth_m FROM pilot_slots WHERE assigned_vendor_id = ? AND is_deleted = 0 AND geometry_crs = 'EPSG:4326'", (vendor_id,)).fetchone()
        assigned = dict(slot) if slot and active and slot["zone_id"] == active["zone_id"] else None
    finally:
        connection.close()
    association = None
    if historical:
        with Path(HISTORICAL_VENDOR_PATH).open(newline="", encoding="utf-8-sig") as source:
            row = next((row for row in csv.DictReader(source) if row.get("vendor_id") == vendor_id), {})
            association = _optional_text(row.get("proposed_zone_id"))
    from backend.services.historical_associations import get_association
    reviewed_association = get_association(vendor_id, database_path)
    return {"profile": profile, "record_source": "HISTORICAL" if historical else "OPERATIONAL",
            "source_division": identity.get("source_division") or (historical.get("preferred_division") if historical else None),
            "historical_proposed_zone_id": association,
            "historical_association": reviewed_association,
            "registration_status": "PROFILE_REGISTERED" if operational else "HISTORICAL_RECORD",
            "account_status": "PHONE_VERIFIED" if account["verified"] else "UNCLAIMED" if account["total"] else "NO_LINKED_IDENTITY",
            "active_allocation": active, "allocations": allocations, "requests": requests, "assigned_slot": assigned}


def vendor_account_information(vendor_id, database_path=DATABASE_PATH, mobile_last4=None):
    """Own-account projection. Never return phones, hashes, sessions or secrets."""
    from backend.repositories.database import connect
    from backend.core.config import get_auth_settings
    from backend.services.authentication import AuthError, normalize_indian_mobile, phone_hmac
    profile = get_vendor_profile(vendor_id, database_path=database_path)
    if profile is None:
        raise OperationalNotFoundError("Vendor profile not found")
    connection = connect(database_path)
    try:
        connection.execute("BEGIN")
        identities = [dict(row) for row in connection.execute("SELECT phone_hash, vendor_source, is_verified FROM vendor_auth_identities WHERE vendor_id = ?", (vendor_id,))]
        overlay = bool(connection.execute("SELECT 1 FROM operational_vendors WHERE vendor_id = ?", (vendor_id,)).fetchone())
        requests = [dict(row) for row in connection.execute("SELECT request_id, zone_id, request_type, status, business_category, preferred_division, created_at, reviewed_at, rejection_reason FROM allocation_requests WHERE vendor_id = ? ORDER BY created_at DESC", (vendor_id,))]
        allocations = [dict(row) for row in connection.execute("SELECT allocation_id, zone_id, request_id, status, allocated_at, released_at, allocation_source FROM allocations WHERE vendor_id = ? ORDER BY allocated_at DESC", (vendor_id,))]
    finally:
        connection.close()
    masked = set()
    if HISTORICAL_IDENTITY_PATH.is_file():
        hashes = {row["phone_hash"] for row in identities}
        with HISTORICAL_IDENTITY_PATH.open(newline="", encoding="utf-8-sig") as source:
            row = next((row for row in csv.DictReader(source) if row.get("vendor_id") == vendor_id), {})
            for key in ("phone_number", "alternate_phone"):
                try:
                    number = normalize_indian_mobile(row.get(key, ""))
                    if phone_hmac(number) in hashes:
                        masked.add("******" + number[-4:])
                except AuthError:
                    pass
    settings = get_auth_settings()
    masked_mobile = f"******{mobile_last4}" if re.fullmatch(r"\d{4}", mobile_last4 or "") else next(iter(masked)) if len(masked) == 1 else None
    return {"profile": profile, "masked_mobile": masked_mobile,
            "authenticated": True, "development_authentication": settings.otp_provider == "development",
            "identity_verification_recorded": any(bool(row["is_verified"]) for row in identities),
            "historical_identity_linked": any(row["vendor_source"] == "HISTORICAL" for row in identities),
            "has_operational_profile": overlay, "phone_change_available": False, "recovery_available": False,
            "requests": requests, "allocations": allocations}


_PROFILE_PHOTO_MAX_BYTES = 2 * 1024 * 1024
def get_vendor_profile_photo(vendor_id, database_path=DATABASE_PATH):
    from backend.repositories.database import connect
    connection = connect(database_path)
    try:
        row = connection.execute(
            "SELECT mime_type, image_base64 FROM vendor_profile_photos WHERE vendor_id = ?",
            (vendor_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return {"data_url": None}
    return {"data_url": f"data:{row['mime_type']};base64,{row['image_base64']}"}


def save_vendor_profile_photo(vendor_id, data_url, database_path=DATABASE_PATH):
    from backend.repositories.database import transaction
    from datetime import datetime, timezone
    if get_vendor_profile(vendor_id, database_path=database_path) is None:
        raise OperationalNotFoundError("Vendor profile not found")
    match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/]+={0,2})", data_url or "")
    if not match:
        raise OperationalValidationError("Choose a JPEG, PNG, or WebP profile photo.")
    mime_type, encoded = match.groups()
    try:
        image = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise OperationalValidationError("The selected profile photo is invalid.") from exc
    if not image or len(image) > _PROFILE_PHOTO_MAX_BYTES:
        raise OperationalValidationError("Profile photos must be smaller than 2 MB.")
    valid_signature = (
        mime_type == "image/jpeg" and image.startswith(b"\xff\xd8\xff")
        or mime_type == "image/png" and image.startswith(b"\x89PNG\r\n\x1a\n")
        or mime_type == "image/webp" and len(image) >= 12 and image.startswith(b"RIFF") and image[8:12] == b"WEBP"
    )
    if not valid_signature:
        raise OperationalValidationError("The photo file does not match its image type.")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with transaction(database_path, immediate=True) as connection:
        connection.execute(
            """INSERT INTO vendor_profile_photos(vendor_id, mime_type, image_base64, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(vendor_id) DO UPDATE SET
                 mime_type = excluded.mime_type,
                 image_base64 = excluded.image_base64,
                 updated_at = excluded.updated_at""",
            (vendor_id, mime_type, encoded, timestamp),
        )
    return {"data_url": f"data:{mime_type};base64,{encoded}"}


def vendor_activity(vendor_id, database_path=DATABASE_PATH):
    """Read factual own-vendor activity; no delivery or unread state is implied."""
    from backend.repositories.database import connect
    if get_vendor_profile(vendor_id, database_path=database_path) is None:
        raise OperationalNotFoundError("Vendor profile not found")
    connection = connect(database_path)
    try:
        requests = [dict(row) for row in connection.execute("SELECT request_id, zone_id, request_type, status, created_at, reviewed_at, updated_at, rejection_reason FROM allocation_requests WHERE vendor_id = ?", (vendor_id,))]
        allocations = [dict(row) for row in connection.execute("SELECT a.*, r.request_type FROM allocations a LEFT JOIN allocation_requests r ON r.request_id = a.request_id WHERE a.vendor_id = ?", (vendor_id,))]
        # Event payloads remain JSON text for schema compatibility. Filtering
        # in Python avoids SQLite json_extract/PostgreSQL JSON operator drift.
        slot_events = [
            row for row in connection.execute(
                "SELECT event_id, zone_id, slot_id, before_json, after_json, created_at FROM pilot_slot_events"
            ).fetchall()
            if json.loads(row["after_json"]).get("assigned_vendor_id") == vendor_id
        ]
        current_slot = connection.execute("""SELECT s.zone_id, s.slot_id FROM pilot_slots s JOIN allocations a ON a.vendor_id = s.assigned_vendor_id AND a.zone_id = s.zone_id AND a.status = 'ACTIVE' JOIN allocation_requests r ON r.request_id = a.request_id AND r.status = 'APPROVED' AND r.vendor_id = a.vendor_id AND r.zone_id = a.zone_id WHERE s.assigned_vendor_id = ? AND s.is_deleted = 0 AND s.geometry_crs = 'EPSG:4326'""", (vendor_id,)).fetchone()
    finally:
        connection.close()
    events = []
    for row in requests:
        base = {"request_id": row["request_id"], "zone_id": row["zone_id"], "status": row["status"], "request_type": row["request_type"]}
        events.append({**base, "id": row["request_id"] + ":submitted", "kind": "SUBMITTED", "timestamp": row["created_at"]})
        if row["status"] in {"APPROVED", "REJECTED", "CANCELLED"}:
            events.append({**base, "id": row["request_id"] + ":decision", "kind": row["status"], "timestamp": row["updated_at"] if row["status"] == "CANCELLED" else row["reviewed_at"], "reason": row["rejection_reason"] if row["status"] == "REJECTED" else None})
    for row in allocations:
        if row["request_type"] == "RELOCATION":
            previous = next((old["zone_id"] for old in allocations if old["status"] == "RELEASED" and old["released_at"] == row["allocated_at"] and old["allocation_id"] != row["allocation_id"]), None)
            events.append({"id": row["allocation_id"], "kind": "RELOCATED", "timestamp": row["allocated_at"], "zone_id": row["zone_id"], "previous_zone_id": previous, "request_id": row["request_id"], "status": row["status"]})
    for row in slot_events:
        before, after = json.loads(row["before_json"]), json.loads(row["after_json"])
        if before.get("assigned_vendor_id") == vendor_id:
            continue
        events.append({"id": "slot:" + str(row["event_id"]), "kind": "SLOT_ASSIGNED", "timestamp": row["created_at"], "zone_id": row["zone_id"], "slot_id": row["slot_id"], "status": after.get("status"), "can_view_slot": bool(current_slot and current_slot["zone_id"] == row["zone_id"] and current_slot["slot_id"] == row["slot_id"])})
    events.sort(key=lambda event: (event["timestamp"] or "", event["id"]), reverse=True)
    return {"events": events, "mode": "ACTIVITY_HISTORY"}
