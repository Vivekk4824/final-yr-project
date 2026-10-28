"""Controlled one-time import of reliable historical mappings as live allocations.

Historical association evidence remains unchanged.  This module creates an
explicit ``LEGACY_IMPORT`` allocation layer only when invoked by the dedicated
script with ``--apply``.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect

from backend.core.data_paths import dataset_path
from backend.repositories.database import (
    DATABASE_PATH,
    DatabaseConnection,
    get_engine,
    transaction,
    utc_now,
)
from backend.services.capacity_analysis import ACCEPTED_ASSOCIATION_SQL


IMPORT_SOURCE = "LEGACY_IMPORT"
PRESERVED_STATUSES = {"CLOSED", "SUSPENDED", "RESTRICTED", "NO_VENDING"}
SOURCE_FILES = [
    str(dataset_path("historical_vendors")),
    str(dataset_path("vendor_registry")),
    str(dataset_path("official_zones")),
    "historical_vendor_zone_associations (operational database)",
]


def _historical_vendor_ids() -> set[str]:
    with Path(dataset_path("historical_vendors")).open(
        newline="", encoding="utf-8-sig"
    ) as source:
        return {
            (row.get("vendor_id") or "").strip()
            for row in csv.DictReader(source)
            if (row.get("vendor_id") or "").strip()
        }


def _official_zone_types() -> dict[str, str]:
    with Path(dataset_path("official_zones")).open(
        newline="", encoding="utf-8-sig"
    ) as source:
        return {
            (row.get("zone_id") or "").strip():
            (row.get("zone_type") or "").strip().upper()
            for row in csv.DictReader(source)
            if (row.get("zone_id") or "").strip()
        }


def deterministic_legacy_allocation_id(vendor_id: str, zone_id: str) -> str:
    raw = f"LEGACY_{vendor_id}_{zone_id}"
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", raw)
    if len(safe) <= 180:
        return safe
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"LEGACY_{digest}"


def _plan_from_connection(db: DatabaseConnection) -> dict[str, Any]:
    historical_ids = _historical_vendor_ids()
    zone_types = _official_zone_types()
    live = {
        row["zone_id"]: dict(row)
        for row in db.execute("SELECT * FROM zone_live_status ORDER BY zone_id")
    }
    associations = {
        row["vendor_id"]: dict(row)
        for row in db.execute(
            "SELECT vendor_id, matched_zone_id, match_status, review_status, "
            "candidate_zone_ids_json, business_category "
            "FROM historical_vendor_zone_associations"
        )
    }
    allocation_rows = [
        dict(row)
        for row in db.execute(
            "SELECT allocation_id, vendor_id, zone_id, request_id, approved_by, "
            "status, allocation_source FROM allocations"
        )
    ]
    active_rows = [row for row in allocation_rows if row["status"] == "ACTIVE"]
    active_by_vendor = {row["vendor_id"]: row for row in active_rows}
    released_by_vendor = {
        row["vendor_id"] for row in allocation_rows if row["status"] == "RELEASED"
    }
    active_by_zone: dict[str, set[str]] = defaultdict(set)
    for row in active_rows:
        active_by_zone[row["zone_id"]].add(row["vendor_id"])

    skipped = Counter()
    candidates: list[dict[str, str]] = []
    existing_active_allocation_wins = 0
    reliable_mapped = 0

    for vendor_id in sorted(historical_ids):
        association = associations.get(vendor_id)
        if association is None:
            skipped["missing_mapping"] += 1
            continue
        accepted = (
            association["match_status"] == "AUTO_MATCHED"
            and association["review_status"] == "UNREVIEWED"
        ) or association["review_status"] in {"CONFIRMED", "CHANGED"}
        if not accepted:
            if association["match_status"] == "REVIEW_REQUIRED":
                skipped["needs_review"] += 1
            else:
                skipped["missing_mapping"] += 1
            continue
        zone_id = (association.get("matched_zone_id") or "").strip()
        if not zone_id:
            skipped["missing_mapping"] += 1
            continue
        reliable_mapped += 1
        if zone_id not in zone_types or zone_id not in live:
            skipped["invalid_zone"] += 1
            continue
        if zone_types[zone_id] == "RESTRICTED":
            skipped["restricted_zone"] += 1
            continue
        if zone_types[zone_id] == "NO_VENDING":
            skipped["no_vending_zone"] += 1
            continue
        if zone_types[zone_id] != "FREE":
            skipped["invalid_zone_type"] += 1
            continue
        active = active_by_vendor.get(vendor_id)
        if active is not None:
            skipped["already_active"] += 1
            if active["zone_id"] != zone_id:
                existing_active_allocation_wins += 1
            continue
        # A released allocation is explicit operational history. Never infer
        # that the older historical association should become ACTIVE again.
        if vendor_id in released_by_vendor:
            skipped["released_history"] += 1
            continue
        candidates.append({
            "vendor_id": vendor_id,
            "zone_id": zone_id,
            "business_category": association.get("business_category") or "",
            "allocation_id": deterministic_legacy_allocation_id(vendor_id, zone_id),
        })

    candidate_by_zone = Counter(row["zone_id"] for row in candidates)
    per_zone = []
    overflow = []
    unknown = []
    for zone_id, imported_count in sorted(candidate_by_zone.items()):
        live_row = live[zone_id]
        before = len(active_by_zone[zone_id])
        after = before + imported_count
        capacity = live_row["official_capacity"]
        overflow_count = 0 if capacity is None else max(0, after - capacity)
        record = {
            "zone_id": zone_id,
            "official_capacity": capacity,
            "active_occupancy_before": before,
            "stored_occupancy_before": live_row["current_vendor_count"],
            "candidate_imports": imported_count,
            "projected_active_occupancy": after,
            "projected_available_capacity": (
                None if capacity is None else max(0, capacity - after)
            ),
            "capacity_overflow": overflow_count > 0,
            "overflow_count": overflow_count,
        }
        per_zone.append(record)
        if record["capacity_overflow"]:
            overflow.append(record)
        if capacity is None:
            unknown.append(record)

    top_affected = sorted(
        per_zone,
        key=lambda row: (-row["candidate_imports"], row["zone_id"]),
    )[:15]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "DRY_RUN",
        "database_backend": db.backend,
        "source_files": SOURCE_FILES,
        "total_historical_vendors": len(historical_ids),
        "association_rows": len(associations),
        "reliable_mapped_vendors": reliable_mapped,
        "already_active": skipped["already_active"],
        "existing_active_allocation_wins": existing_active_allocation_wins,
        "candidate_count": len(candidates),
        "imported_count": 0,
        "skipped_counts": dict(sorted(skipped.items())),
        "_candidate_allocations": candidates,
        "per_zone_occupancy": per_zone,
        "capacity_overflow_zones": overflow,
        "unknown_capacity_zones": unknown,
        "top_affected_zones": top_affected,
        "errors": [],
    }


def build_legacy_import_plan(database_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    """Build a read-only import plan. It performs no schema or data writes."""
    connection = DatabaseConnection(get_engine(database_path).connect())
    try:
        plan = _plan_from_connection(connection)
        plan.pop("_candidate_allocations", None)
        return plan
    finally:
        connection.close()


def _prepare_apply_schema(db: DatabaseConnection) -> None:
    """Add source metadata and relax only the obsolete overflow constraint."""
    inspector = inspect(db.raw)
    allocation_columns = {column["name"] for column in inspector.get_columns("allocations")}
    if "allocation_source" not in allocation_columns:
        db.execute(
            "ALTER TABLE allocations ADD COLUMN allocation_source "
            "TEXT NOT NULL DEFAULT 'ADMIN_APPROVED'"
        )

    if db.backend != "postgresql":
        # Fresh/disposable SQLite schemas already use the v2 constraints.  The
        # user's SQLite backup is intentionally never migrated by this script.
        return

    inspector = inspect(db.raw)
    preparer = db.raw.dialect.identifier_preparer
    checks = inspector.get_check_constraints("zone_live_status")
    for check in checks:
        sql = (check.get("sqltext") or "").lower().replace("\n", " ")
        name = check.get("name")
        obsolete = (
            "current_vendor_count <= official_capacity" in sql
            or "available_capacity = (official_capacity - current_vendor_count)" in sql
            or "current_vendor_count <> official_capacity" in sql
            or name in {
                "ck_zone_live_status_capacity_consistency_v2",
                "ck_zone_live_status_full_at_or_over_capacity_v2",
            }
        )
        if obsolete and name:
            db.execute(
                f"ALTER TABLE zone_live_status DROP CONSTRAINT {preparer.quote(name)}"
            )
    db.execute(
        "ALTER TABLE zone_live_status ADD CONSTRAINT "
        "ck_zone_live_status_capacity_consistency_v2 CHECK ("
        "(official_capacity IS NULL AND available_capacity IS NULL) OR "
        "(official_capacity IS NOT NULL AND available_capacity = CASE "
        "WHEN current_vendor_count >= official_capacity THEN 0 "
        "ELSE official_capacity - current_vendor_count END))"
    )
    db.execute(
        "ALTER TABLE zone_live_status ADD CONSTRAINT "
        "ck_zone_live_status_full_at_or_over_capacity_v2 CHECK ("
        "official_capacity IS NULL OR current_vendor_count < official_capacity "
        "OR status IN ('FULL','CLOSED','SUSPENDED','RESTRICTED','NO_VENDING'))"
    )

    allocation_checks = inspect(db.raw).get_check_constraints("allocations")
    if not any(check.get("name") == "ck_allocations_source" for check in allocation_checks):
        db.execute(
            "ALTER TABLE allocations ADD CONSTRAINT ck_allocations_source "
            "CHECK (allocation_source IN ('ADMIN_APPROVED', 'LEGACY_IMPORT'))"
        )


def _recalculate_with_connection(db: DatabaseConnection, now: str) -> list[dict[str, Any]]:
    active_counts = {
        row["zone_id"]: row["vendor_count"]
        for row in db.execute(
            "SELECT zone_id, COUNT(DISTINCT vendor_id) AS vendor_count "
            "FROM allocations WHERE status = 'ACTIVE' GROUP BY zone_id"
        )
    }
    changes = []
    for zone in db.execute("SELECT * FROM zone_live_status ORDER BY zone_id"):
        count = int(active_counts.get(zone["zone_id"], 0))
        capacity = zone["official_capacity"]
        available = None if capacity is None else max(0, capacity - count)
        status = zone["status"]
        if status not in PRESERVED_STATUSES and capacity is not None:
            status = "FULL" if count >= capacity else "OPEN"
        db.execute(
            "UPDATE zone_live_status SET current_vendor_count = ?, "
            "available_capacity = ?, status = ?, updated_at = ? WHERE zone_id = ?",
            (count, available, status, now, zone["zone_id"]),
        )
        changes.append({
            "zone_id": zone["zone_id"],
            "official_capacity": capacity,
            "current_vendor_count": count,
            "available_capacity": available,
            "status": status,
            "capacity_overflow": capacity is not None and count > capacity,
            "overflow_count": 0 if capacity is None else max(0, count - capacity),
        })
    return changes


def recalculate_zone_occupancy_from_active_allocations(
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    """Repair live counters deterministically from all ACTIVE allocations."""
    with transaction(database_path, immediate=True) as db:
        _prepare_apply_schema(db)
        return _recalculate_with_connection(db, utc_now())


def apply_legacy_import(database_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    """Atomically import the current reliable plan and rebuild occupancy."""
    with transaction(database_path, immediate=True) as db:
        if db.backend == "postgresql":
            db.execute("LOCK TABLE allocations IN SHARE ROW EXCLUSIVE MODE")
        _prepare_apply_schema(db)
        plan = _plan_from_connection(db)
        candidates = plan.pop("_candidate_allocations")
        now = utc_now()
        imported = 0
        for candidate in candidates:
            result = db.execute(
                "INSERT INTO allocations (allocation_id, vendor_id, zone_id, request_id, "
                "status, allocated_at, released_at, approved_by, allocation_source, "
                "created_at, updated_at) VALUES (?, ?, ?, NULL, 'ACTIVE', ?, NULL, NULL, "
                "'LEGACY_IMPORT', ?, ?) ON CONFLICT DO NOTHING",
                (
                    candidate["allocation_id"], candidate["vendor_id"],
                    candidate["zone_id"], now, now, now,
                ),
            )
            imported += max(0, result.rowcount)

        occupancy = _recalculate_with_connection(db, now)
        audit_details = {
            "allocation_source": IMPORT_SOURCE,
            "candidate_count": plan["candidate_count"],
            "imported_count": imported,
            "skipped_counts": plan["skipped_counts"],
            "overflow_zone_count": sum(row["capacity_overflow"] for row in occupancy),
        }
        db.execute(
            "INSERT INTO admin_audit_log (audit_id, action, entity_type, entity_id, "
            "performed_by, details_json, created_at) VALUES (?, 'LEGACY_ALLOCATION_IMPORT', "
            "'migration_batch', ?, NULL, ?, ?)",
            (
                f"AUD_{uuid.uuid4().hex}", f"LEGACY_IMPORT_{now}",
                json.dumps(audit_details, sort_keys=True), now,
            ),
        )
        plan["mode"] = "APPLY"
        plan["imported_count"] = imported
        plan["post_import_zone_occupancy"] = occupancy
        plan["capacity_overflow_zones"] = [
            row for row in occupancy if row["capacity_overflow"]
        ]
        plan["unknown_capacity_zones"] = [
            row for row in occupancy
            if row["official_capacity"] is None and row["current_vendor_count"] > 0
        ]
        return plan


def active_vendor_category_counts(
    business_category: str,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, dict[str, int]]:
    """Return live total/category counts, resolving legacy categories in place."""
    db = DatabaseConnection(get_engine(database_path).connect())
    try:
        rows = db.execute(
            "SELECT a.zone_id, a.vendor_id, "
            "COALESCE(o.business_category, h.business_category) AS business_category "
            "FROM allocations AS a "
            "LEFT JOIN operational_vendors AS o ON o.vendor_id = a.vendor_id "
            "LEFT JOIN historical_vendor_zone_associations AS h ON h.vendor_id = a.vendor_id "
            "WHERE a.status = 'ACTIVE'"
        ).fetchall()
    finally:
        db.close()
    totals: dict[str, set[str]] = defaultdict(set)
    matching: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        totals[row["zone_id"]].add(row["vendor_id"])
        if row["business_category"] == business_category:
            matching[row["zone_id"]].add(row["vendor_id"])
    return {
        zone_id: {
            "current_total_vendors": len(vendors),
            "current_same_category_vendors": len(matching[zone_id]),
        }
        for zone_id, vendors in totals.items()
    }


def current_total_vendors(zone_id: str, database_path: str | Path = DATABASE_PATH) -> int:
    counts = active_vendor_category_counts("", database_path)
    return counts.get(zone_id, {}).get("current_total_vendors", 0)


def current_same_category_vendors(
    zone_id: str,
    business_category: str,
    database_path: str | Path = DATABASE_PATH,
) -> int:
    counts = active_vendor_category_counts(business_category, database_path)
    return counts.get(zone_id, {}).get("current_same_category_vendors", 0)

