"""Read-only reconciliation of accepted historical evidence and allocations.

The audit never treats historical association rows as current occupancy and
never changes operational data.  It classifies by stable ``vendor_id`` only;
names, phone numbers and fuzzy matching are deliberately excluded.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from backend.core.data_paths import dataset_path
from backend.repositories.database import DATABASE_PATH, connect
from backend.services.capacity_analysis import ACCEPTED_ASSOCIATION_SQL


CLASSIFICATIONS = (
    "active_legacy_same_zone",
    "active_approved_same_zone",
    "active_allocation_different_zone",
    "released_or_relocated",
    "duplicate_association",
    "unresolved_identity_or_zone",
    "not_eligible_under_import_policy",
    "eligible_but_missing",
    "requires_human_verification",
)


def _historical_ids() -> set[str]:
    with Path(dataset_path("historical_vendors")).open(
        newline="", encoding="utf-8-sig"
    ) as source:
        return {
            (row.get("vendor_id") or "").strip()
            for row in csv.DictReader(source)
            if (row.get("vendor_id") or "").strip()
        }


def audit_historical_occupancy(
    database_path: str | Path = DATABASE_PATH,
    *,
    zone_id: str | None = None,
) -> dict[str, Any]:
    """Classify accepted association rows without changing the database."""
    db = connect(database_path)
    try:
        if db.backend == "postgresql":
            db.execute("SET TRANSACTION READ ONLY")
        live_rows = [dict(row) for row in db.execute(
            "SELECT zone_id, official_capacity, current_vendor_count, "
            "available_capacity, status FROM zone_live_status ORDER BY zone_id"
        )]
        all_association_rows = [dict(row) for row in db.execute(
            "SELECT vendor_id, matched_zone_id, match_status, review_status, "
            "candidate_zone_ids_json, business_category "
            "FROM historical_vendor_zone_associations ORDER BY vendor_id"
        )]
        association_rows = [dict(row) for row in db.execute(
            f"SELECT vendor_id, matched_zone_id, match_status, review_status, "
            f"business_category FROM historical_vendor_zone_associations "
            f"WHERE matched_zone_id IS NOT NULL AND {ACCEPTED_ASSOCIATION_SQL} "
            f"ORDER BY vendor_id"
        )]
        unresolved_count = int(db.execute(
            "SELECT COUNT(*) AS total FROM historical_vendor_zone_associations "
            "WHERE match_status = 'REVIEW_REQUIRED' AND review_status = 'UNREVIEWED'"
        ).fetchone()["total"])
        allocation_rows = [dict(row) for row in db.execute(
            "SELECT allocation_id, vendor_id, zone_id, status, allocation_source, "
            "allocated_at, released_at FROM allocations ORDER BY vendor_id, allocated_at"
        )]
        if db.backend == "postgresql":
            db.rollback()
    finally:
        db.close()

    official_types: dict[str, str] = {}
    with Path(dataset_path("official_zones")).open(
        newline="", encoding="utf-8-sig"
    ) as source:
        for row in csv.DictReader(source):
            official_types[(row.get("zone_id") or "").strip()] = (
                row.get("zone_type") or ""
            ).strip().upper()

    historical_ids = _historical_ids()
    association_by_vendor = {row["vendor_id"]: row for row in all_association_rows}
    live_by_zone = {row["zone_id"]: row for row in live_rows}
    allocations_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    active_by_zone: dict[str, set[str]] = defaultdict(set)
    active_source_counts: Counter[str] = Counter()
    for allocation in allocation_rows:
        allocations_by_vendor[allocation["vendor_id"]].append(allocation)
        if allocation["status"] == "ACTIVE":
            active_by_zone[allocation["zone_id"]].add(allocation["vendor_id"])
            active_source_counts[allocation.get("allocation_source") or "UNSPECIFIED"] += 1

    association_frequency = Counter(row["vendor_id"] for row in association_rows)
    accepted_unique_by_zone: dict[str, set[str]] = defaultdict(set)
    classified: dict[str, Counter[str]] = defaultdict(Counter)
    eligible_missing_by_zone: dict[str, set[str]] = defaultdict(set)
    category_missing_by_zone: dict[str, Counter[str]] = defaultdict(Counter)
    import_policy_exclusions: Counter[str] = Counter()

    for association in association_rows:
        vendor_id = association["vendor_id"]
        target = association["matched_zone_id"]
        accepted_unique_by_zone[target].add(vendor_id)
        history = allocations_by_vendor[vendor_id]
        active = [row for row in history if row["status"] == "ACTIVE"]
        if association_frequency[vendor_id] > 1:
            classification = "duplicate_association"
        elif active:
            same = next((row for row in active if row["zone_id"] == target), None)
            if same and same["allocation_source"] == "LEGACY_IMPORT":
                classification = "active_legacy_same_zone"
            elif same and same["allocation_source"] == "ADMIN_APPROVED":
                classification = "active_approved_same_zone"
            else:
                classification = "active_allocation_different_zone"
        elif any(row["status"] == "RELEASED" for row in history):
            classification = "released_or_relocated"
        elif vendor_id not in historical_ids or target not in live_by_zone:
            classification = "unresolved_identity_or_zone"
        elif official_types.get(target) != "FREE":
            classification = "not_eligible_under_import_policy"
            zone_type = official_types.get(target) or "UNKNOWN"
            import_policy_exclusions[
                {
                    "RESTRICTED": "restricted_zone",
                    "NO_VENDING": "no_vending_zone",
                }.get(zone_type, "non_free_or_unknown_zone")
            ] += 1
        elif association["match_status"] == "REVIEW_REQUIRED" and association["review_status"] == "UNREVIEWED":
            classification = "requires_human_verification"
        else:
            classification = "eligible_but_missing"
            eligible_missing_by_zone[target].add(vendor_id)
            category_missing_by_zone[target][association.get("business_category") or "unknown"] += 1
        classified[target][classification] += 1

    model_evidence_by_zone: dict[str, list[dict[str, str]]] = defaultdict(list)
    with Path(dataset_path("vendor_registry")).open(
        newline="", encoding="utf-8-sig"
    ) as source:
        for row in csv.DictReader(source):
            if row.get("match_status") == "text_association" and row.get("proposed_zone_id"):
                model_evidence_by_zone[row["proposed_zone_id"]].append(row)

    def model_evidence_summary(target: str) -> dict[str, Any]:
        rows = model_evidence_by_zone[target]
        vendors = {row["vendor_id"] for row in rows}
        reconciled = Counter()
        active_state = Counter()
        for vendor_id in vendors:
            association = association_by_vendor.get(vendor_id)
            if association is None:
                reconciled["missing_reconciliation_row"] += 1
            elif association["matched_zone_id"] == target and (
                (association["match_status"] == "AUTO_MATCHED" and association["review_status"] == "UNREVIEWED")
                or association["review_status"] in {"CONFIRMED", "CHANGED"}
            ):
                reconciled["accepted_same_zone"] += 1
            elif association["review_status"] in {"CONFIRMED", "CHANGED"} or association["match_status"] == "AUTO_MATCHED":
                reconciled["accepted_different_zone"] += 1
            elif association["match_status"] == "REVIEW_REQUIRED":
                reconciled["requires_human_verification"] += 1
            else:
                reconciled["unmatched"] += 1
            active = [row for row in allocations_by_vendor[vendor_id] if row["status"] == "ACTIVE"]
            if not active:
                active_state["no_active_allocation"] += 1
            elif any(row["zone_id"] == target for row in active):
                active_state["active_same_zone"] += 1
            else:
                active_state["active_different_zone"] += 1
        return {
            "text_association_rows": len(rows),
            "unique_vendor_ids": len(vendors),
            "reconciled_classification": dict(sorted(reconciled.items())),
            "operational_allocation_classification": dict(sorted(active_state.items())),
        }

    zones: list[dict[str, Any]] = []
    for live in live_rows:
        target = live["zone_id"]
        if zone_id and target != zone_id:
            continue
        counts = {key: int(classified[target][key]) for key in CLASSIFICATIONS}
        active_count = len(active_by_zone[target])
        expected = active_count + len(eligible_missing_by_zone[target])
        capacity = live["official_capacity"]
        zones.append({
            "zone_id": target,
            "official_capacity": capacity,
            "stored_current_vendor_count": live["current_vendor_count"],
            "derived_active_operational_count": active_count,
            "stored_available_capacity": live["available_capacity"],
            "derived_available_capacity": None if capacity is None else max(0, capacity - active_count),
            "accepted_unique_historical_vendors": len(accepted_unique_by_zone[target]),
            "accepted_association_rows": sum(counts.values()),
            **counts,
            "eligible_missing_category_counts": dict(sorted(category_missing_by_zone[target].items())),
            "expected_count_after_approved_reconciliation": expected,
            "expected_available_after_approved_reconciliation": (
                None if capacity is None else max(0, capacity - expected)
            ),
            "projected_over_capacity_by": (
                None if capacity is None else max(0, expected - capacity)
            ),
            "stored_counter_matches_active_allocations": live["current_vendor_count"] == active_count,
            "live_status": live["status"],
            "legacy_model_text_evidence": model_evidence_summary(target),
        })

    city = Counter()
    for counts in classified.values():
        city.update(counts)
    return {
        "mode": "READ_ONLY_DRY_RUN",
        "database_backend": db.backend,
        "zone_filter": zone_id,
        "accepted_association_rows": len(association_rows),
        "unresolved_review_required_rows": unresolved_count,
        "active_allocation_count": sum(len(vendors) for vendors in active_by_zone.values()),
        "active_allocation_source_counts": dict(sorted(active_source_counts.items())),
        "classification_counts": {key: int(city[key]) for key in CLASSIFICATIONS},
        "import_policy_exclusion_reasons": dict(sorted(import_policy_exclusions.items())),
        "eligible_missing_count": sum(len(ids) for ids in eligible_missing_by_zone.values()),
        "zones_with_stored_counter_mismatch": sum(
            not row["stored_counter_matches_active_allocations"] for row in zones
        ),
        "zones_currently_over_capacity": sum(
            (row["projected_over_capacity_by"] or 0) > 0 for row in zones
        ),
        "zones": zones,
        "notice": (
            "Historical associations remain evidence. Only unique ACTIVE allocations count as "
            "operational occupancy; no database changes were made."
        ),
    }

