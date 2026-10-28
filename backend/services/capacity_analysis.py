"""Authoritative derived operational and historical planning capacity metrics.

Historical evidence never consumes operational capacity.  Every value here is
derived in bulk from official live rows, all ACTIVE allocations, and
accepted historical associations; no competing counters are persisted.
"""
from __future__ import annotations

import json
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from backend.repositories.database import DATABASE_PATH, connect
from backend.core.data_paths import dataset_path


NEAR_CAPACITY_RATIO = 0.80
ACCEPTED_ASSOCIATION_SQL = (
    "((match_status = 'AUTO_MATCHED' AND review_status = 'UNREVIEWED') "
    "OR review_status IN ('CONFIRMED', 'CHANGED'))"
)


def _capacity_values(capacity: int | None, operational_occupancy: int,
                     historical_planning_count: int) -> dict[str, Any]:
    planning_load = operational_occupancy + historical_planning_count
    if capacity is None:
        operational_available = planning_available = planning_overcapacity = None
        near_capacity = operational_at_capacity = False
        pressure_status = "CAPACITY_UNKNOWN"
    else:
        operational_available = max(0, capacity - operational_occupancy)
        planning_available = max(0, capacity - planning_load)
        planning_overcapacity = max(0, planning_load - capacity)
        operational_at_capacity = operational_occupancy >= capacity
        near_capacity = capacity > 0 and planning_load < capacity and planning_load / capacity >= NEAR_CAPACITY_RATIO
        if planning_overcapacity > 0:
            pressure_status = "ESTIMATED_PLANNING_OVERCAPACITY"
        elif operational_at_capacity:
            pressure_status = "OPERATIONALLY_AT_CAPACITY"
        elif near_capacity:
            pressure_status = "NEAR_ESTIMATED_PLANNING_CAPACITY"
        else:
            pressure_status = "WITHIN_LISTED_CAPACITY"
    return {
        "operational_occupancy": operational_occupancy,
        "operational_available": operational_available,
        "historical_planning_count": historical_planning_count,
        "planning_load": planning_load,
        "planning_available": planning_available,
        "planning_overcapacity": planning_overcapacity,
        "operational_at_capacity": operational_at_capacity,
        "near_planning_capacity": near_capacity,
        "capacity_pressure_status": pressure_status,
    }


def zone_capacity_analysis(database_path: str | Path = DATABASE_PATH) -> dict[str, dict[str, Any]]:
    """Return one complete, deterministic capacity record for every official zone."""
    db = connect(database_path)
    try:
        live_allocation_rows = [dict(row) for row in db.execute(
            """SELECT z.zone_id, z.official_capacity, z.status, z.verified_at,
                      z.verified_by, z.updated_at, a.vendor_id AS active_vendor_id
               FROM zone_live_status AS z
               LEFT JOIN allocations AS a
                 ON a.zone_id = z.zone_id AND a.status = 'ACTIVE'
               ORDER BY z.zone_id"""
        )]
        association_rows = [dict(row) for row in db.execute(
            """SELECT vendor_id, matched_zone_id, business_category, match_status,
                      review_status, candidate_zone_ids_json
               FROM historical_vendor_zone_associations"""
        )]
    finally:
        db.close()

    live_by_zone: dict[str, dict[str, Any]] = {}
    active_by_zone: dict[str, set[str]] = defaultdict(set)
    active_vendor_ids: set[str] = set()
    for row in live_allocation_rows:
        live_by_zone.setdefault(row["zone_id"], {
            key: row[key] for key in (
                "zone_id", "official_capacity", "status", "verified_at", "verified_by", "updated_at"
            )
        })
        if row.get("active_vendor_id"):
            active_by_zone[row["zone_id"]].add(row["active_vendor_id"])
            active_vendor_ids.add(row["active_vendor_id"])

    accepted_rows = [row for row in association_rows if row.get("matched_zone_id") and (
        (row["match_status"] == "AUTO_MATCHED" and row["review_status"] == "UNREVIEWED")
        or row["review_status"] in {"CONFIRMED", "CHANGED"}
    )]
    unresolved_rows = [row for row in association_rows if
                       row["match_status"] == "REVIEW_REQUIRED" and row["review_status"] == "UNREVIEWED"]
    association_total = len(association_rows)
    accepted_by_zone: dict[str, set[str]] = defaultdict(set)
    planning_by_zone: dict[str, set[str]] = defaultdict(set)
    categories_by_zone: dict[str, Counter[str]] = defaultdict(Counter)
    for row in accepted_rows:
        zone_id, vendor_id = row["matched_zone_id"], row["vendor_id"]
        accepted_by_zone[zone_id].add(vendor_id)
        if vendor_id not in active_vendor_ids:
            planning_by_zone[zone_id].add(vendor_id)
            categories_by_zone[zone_id][row.get("business_category") or "unknown"] += 1

    unresolved_by_zone: dict[str, set[str]] = defaultdict(set)
    for row in unresolved_rows:
        try:
            candidates = json.loads(row.get("candidate_zone_ids_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            candidates = []
        for zone_id in candidates:
            unresolved_by_zone[str(zone_id)].add(row["vendor_id"])

    with Path(dataset_path("historical_vendors")).open(newline="", encoding="utf-8-sig") as source:
        expected_vendor_ids = {row["vendor_id"] for row in csv.DictReader(source) if row.get("vendor_id")}
    complete_registry = association_total == len(expected_vendor_ids)
    result: dict[str, dict[str, Any]] = {}
    for live in live_by_zone.values():
        zone_id = live["zone_id"]
        capacity = live["official_capacity"]
        operational = len(active_by_zone[zone_id])
        historical_planning = len(planning_by_zone[zone_id])
        unresolved_count = len(unresolved_by_zone[zone_id])
        if unresolved_count:
            evidence_status = "INCOMPLETE_UNRESOLVED_CANDIDATES"
        elif not accepted_by_zone[zone_id]:
            evidence_status = "NO_ACCEPTED_HISTORICAL_EVIDENCE"
        else:
            evidence_status = "ACCEPTED_EVIDENCE_ONLY"
        result[zone_id] = {
            "zone_id": zone_id,
            "listed_official_capacity": capacity,
            **_capacity_values(capacity, operational, historical_planning),
            "accepted_historical_association_count": len(accepted_by_zone[zone_id]),
            "historical_business_categories": dict(sorted(categories_by_zone[zone_id].items())),
            "unresolved_candidate_count": unresolved_count,
            "historical_evidence_status": evidence_status,
            "historical_registry_complete": complete_registry,
            "live_status": live["status"],
            "verified_at": live["verified_at"],
            "verified_by": live["verified_by"],
            "notice": "Historical planning load is decision-support evidence, not verified occupancy or an allocation.",
        }
    return result


def capacity_pressure_summary(
    database_path: str | Path = DATABASE_PATH,
    *,
    include_zones: bool = True,
) -> dict[str, Any]:
    if include_zones:
        records = list(zone_capacity_analysis(database_path).values())
    else:
        db = connect(database_path)
        try:
            rows = [dict(row) for row in db.execute(
                f"""WITH active_vendors AS (
                         SELECT DISTINCT vendor_id FROM allocations WHERE status = 'ACTIVE'
                       ), active AS (
                         SELECT zone_id, COUNT(DISTINCT vendor_id) AS operational_occupancy
                         FROM allocations WHERE status = 'ACTIVE' GROUP BY zone_id
                       ), accepted AS (
                         SELECT h.matched_zone_id AS zone_id,
                                COUNT(DISTINCT h.vendor_id) AS accepted_count,
                                COUNT(DISTINCT CASE WHEN av.vendor_id IS NULL THEN h.vendor_id END)
                                  AS historical_planning_count
                         FROM historical_vendor_zone_associations AS h
                         LEFT JOIN active_vendors AS av ON av.vendor_id = h.vendor_id
                         WHERE h.matched_zone_id IS NOT NULL AND {ACCEPTED_ASSOCIATION_SQL}
                         GROUP BY h.matched_zone_id
                       )
                       SELECT z.zone_id, z.official_capacity, z.status AS live_status,
                              COALESCE(a.operational_occupancy, 0) AS operational_occupancy,
                              COALESCE(h.accepted_count, 0) AS accepted_count,
                              COALESCE(h.historical_planning_count, 0) AS historical_planning_count
                       FROM zone_live_status AS z
                       LEFT JOIN active AS a ON a.zone_id = z.zone_id
                       LEFT JOIN accepted AS h ON h.zone_id = z.zone_id
                       ORDER BY z.zone_id"""
            )]
            unresolved_rows = [dict(row) for row in db.execute(
                """SELECT vendor_id, candidate_zone_ids_json
                   FROM historical_vendor_zone_associations
                   WHERE match_status = 'REVIEW_REQUIRED' AND review_status = 'UNREVIEWED'"""
            )]
        finally:
            db.close()
        unresolved_zones: set[str] = set()
        for row in unresolved_rows:
            try:
                unresolved_zones.update(str(value) for value in json.loads(row.get("candidate_zone_ids_json") or "[]"))
            except (TypeError, json.JSONDecodeError):
                continue
        records = []
        for row in rows:
            capacity = row["official_capacity"]
            operational = int(row["operational_occupancy"])
            planning = int(row["historical_planning_count"])
            records.append({
                **row,
                **_capacity_values(capacity, operational, planning),
                "historical_evidence_status": (
                    "INCOMPLETE_UNRESOLVED_CANDIDATES" if row["zone_id"] in unresolved_zones
                    else "NO_ACCEPTED_HISTORICAL_EVIDENCE" if not row["accepted_count"]
                    else "ACCEPTED_EVIDENCE_ONLY"
                ),
            })
    over = [row for row in records if (row["planning_overcapacity"] or 0) > 0]
    near = [row for row in records if row["near_planning_capacity"]]
    operational_full = [row for row in records if row["operational_at_capacity"]]
    incomplete = [row for row in records if row["historical_evidence_status"] != "ACCEPTED_EVIDENCE_ONLY"]
    result = {
        "near_capacity_ratio": NEAR_CAPACITY_RATIO,
        "zone_count": len(records),
        "planning_overcapacity_zone_count": len(over),
        "near_planning_capacity_zone_count": len(near),
        "operationally_at_capacity_zone_count": len(operational_full),
        "incomplete_historical_evidence_zone_count": len(incomplete),
        "notice": "Estimated historical pressure is not verified congestion, illegal vending, or operational occupancy.",
    }
    if include_zones:
        result["zones"] = records
    else:
        result["_live_status_counts"] = dict(Counter(row["live_status"] for row in records))
    return result


def zone_historical_vendors(zone_id: str, database_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    """Return accepted registry profiles for one zone with operational state kept separate."""
    db = connect(database_path)
    try:
        associations = [dict(row) for row in db.execute(
            f"""SELECT * FROM historical_vendor_zone_associations
                 WHERE matched_zone_id = ? AND {ACCEPTED_ASSOCIATION_SQL}
                 ORDER BY vendor_id""",
            (zone_id,),
        )]
        operational = {row["vendor_id"]: dict(row) for row in db.execute(
            "SELECT vendor_id, application_vendor_id, full_name, business_name FROM operational_vendors"
        )}
        accounts = {row["vendor_id"]: bool(row["verified"]) for row in db.execute(
            "SELECT vendor_id, MAX(is_verified) AS verified FROM vendor_auth_identities GROUP BY vendor_id"
        )}
        account_ids = {row["vendor_id"] for row in db.execute(
            "SELECT DISTINCT vendor_id FROM vendor_auth_identities"
        )}
        active = {row["vendor_id"]: dict(row) for row in db.execute(
            """SELECT vendor_id, allocation_id, zone_id, allocated_at,
                      allocation_source
               FROM allocations WHERE status = 'ACTIVE'"""
        )}
    finally:
        db.close()

    wanted = {row["vendor_id"] for row in associations}
    historical_profiles = {}
    with Path(dataset_path("historical_vendors")).open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row.get("vendor_id") in wanted:
                historical_profiles[row["vendor_id"]] = row

    vendors = []
    for association in associations:
        vendor_id = association["vendor_id"]
        source = historical_profiles.get(vendor_id, {})
        overlay = operational.get(vendor_id)
        allocation = active.get(vendor_id)
        vendors.append({
            "vendor_id": vendor_id,
            "application_vendor_id": overlay.get("application_vendor_id") if overlay else None,
            "full_name": (overlay.get("full_name") if overlay else None) or source.get("vendor_name_english"),
            "business_name": overlay.get("business_name") if overlay else None,
            "business_category": association.get("business_category"),
            "recorded_division": association.get("recorded_division"),
            "original_location_text": association.get("original_location_text"),
            "location_text_english": association.get("location_text_english"),
            "match_status": association.get("match_status"),
            "review_status": association.get("review_status"),
            "registration_status": "PROFILE_REGISTERED" if overlay else "HISTORICAL_REGISTRY_PROFILE",
            "account_status": "PHONE_VERIFIED" if accounts.get(vendor_id) else "UNCLAIMED" if vendor_id in account_ids else "NO_LINKED_IDENTITY",
            "active_allocation": allocation,
            "included_in_historical_planning_load": allocation is None,
        })
    return {
        "zone_id": zone_id,
        "count": len(vendors),
        "vendors": vendors,
        "notice": "Accepted historical location evidence only; this is not current occupancy. Active allocations are identified separately and are not double-counted in planning load.",
    }

