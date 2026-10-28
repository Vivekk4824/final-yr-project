"""Evidence-based historical vendor-to-zone reconciliation and admin review.

Historical associations are descriptive source evidence.  They never update
allocations, occupancy, capacity, slot assignments, or recommendation inputs.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
import uuid
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from backend.core.data_paths import dataset_path
from backend.repositories.database import (
    DATABASE_PATH,
    OperationalNotFoundError,
    OperationalValidationError,
    connect,
    initialize_schema,
    transaction,
    utc_now,
)


ALGORITHM_VERSION = "historical-zone-resolution-v1"
ACCEPTED_REVIEW_STATUSES = {"CONFIRMED", "CHANGED"}
REVIEWED_CROSSWALK_STATUSES = {"CONFIRMED", "APPROVED", "REVIEWED", "ACCEPTED"}
LANDMARK_WORDS = {
    "market", "bazar", "bazaar", "temple", "mandir", "school", "hospital",
    "mall", "garden", "track", "bridge", "depot", "station", "dargah",
    "masjid", "church", "ground", "complex", "society", "college", "theatre",
    "चौक", "मार्केट", "बाजार", "मंदिर", "शाळा", "रस्ता",
}
COMMON_LOCATION_WORDS = {
    "the", "at", "in", "on", "of", "to", "from", "near", "beside", "along",
    "within", "opposite", "behind", "front", "side", "area", "space", "open",
    "road", "street", "chowk", "market", "bazar", "bazaar", "vegetable",
    "nagar", "gaon", "village", "colony", "corner", "east", "west", "north",
    "south", "old", "new", "nmc", "bus", "stop", "service", "footpath",
}


def normalize_location(value: Any) -> str:
    """Deterministically normalize Marathi/English location text for comparison."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    replacements = {
        r"\brd\.?\b": " road ", r"\bst\.?\b": " street ",
        r"\bchowk\b": " chowk ", r"\bchauk\b": " chowk ",
        r"\bbazaar\b": " bazar ", r"\bmkt\.?\b": " market ",
        r"\bft\.?\b": " feet ",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    # Indic vowel signs and anusvara are combining marks rather than standalone
    # alphanumerics; retaining Unicode mark categories prevents Marathi words
    # from being split or silently changed during normalization.
    text = "".join(
        character if character.isalnum() or unicodedata.category(character).startswith("M") else " "
        for character in text
    )
    return " ".join(text.split())


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _candidate_ids(value: Any, official_ids: set[str]) -> list[str]:
    result = []
    for candidate in re.split(r"\s*\|\s*|\s*,\s*", str(value or "").strip()):
        if candidate in official_ids and candidate not in result:
            result.append(candidate)
    return result


def _distinctive_landmark_match(alias: str, description: str) -> bool:
    alias_tokens = set(normalize_location(alias).split())
    description_tokens = set(normalize_location(description).split())
    distinctive = alias_tokens - COMMON_LOCATION_WORDS
    overlap = distinctive & description_tokens
    has_landmark = bool(alias_tokens & LANDMARK_WORDS)
    return bool(overlap) and (has_landmark or len(overlap) >= 2)


def _rank_text_candidates(location: str, division: str, zones: list[dict[str, str]]) -> list[str]:
    """Return transparent suggestions only; these are never auto-confirmed."""
    source = normalize_location(location)
    if not source:
        return []
    source_tokens = set(source.split()) - COMMON_LOCATION_WORDS
    ranked = []
    for zone in zones:
        if division and zone.get("division") != division:
            continue
        description = normalize_location(zone.get("official_description"))
        description_tokens = set(description.split()) - COMMON_LOCATION_WORDS
        overlap = len(source_tokens & description_tokens)
        if not overlap:
            continue
        similarity = SequenceMatcher(None, source, description).ratio()
        ranked.append((overlap, similarity, zone["zone_id"]))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[2] for item in ranked[:3]]


def _existing_associations(database_path=DATABASE_PATH) -> dict[str, dict[str, Any]]:
    initialize_schema(database_path)
    db = connect(database_path)
    try:
        return {row["vendor_id"]: dict(row) for row in db.execute(
            "SELECT * FROM historical_vendor_zone_associations"
        )}
    finally:
        db.close()


def reconcile_historical_associations(database_path=DATABASE_PATH) -> dict[str, Any]:
    """Build a complete dry-run result for every historical vendor."""
    vendors = _read_rows(dataset_path("historical_vendors"))
    registry = {row["vendor_id"]: row for row in _read_rows(dataset_path("vendor_registry"))}
    crosswalk = {row["location_group_id"]: row for row in _read_rows(dataset_path("crosswalk"))}
    zones = _read_rows(dataset_path("official_zones"))
    zone_by_id = {row["zone_id"]: row for row in zones}
    official_ids = set(zone_by_id)
    existing = _existing_associations(database_path)

    alias_targets: dict[str, set[str]] = {}
    for row in crosswalk.values():
        reviewed_zone_id = row.get("reviewed_zone_id", "").strip()
        review_status = row.get("review_status", "").strip().upper()
        zone_id = reviewed_zone_id if review_status in REVIEWED_CROSSWALK_STATUSES else row.get("proposed_zone_id", "").strip()
        for value in (row.get("business_location_english"), row.get("business_location_normalized")):
            alias = normalize_location(value)
            if alias and zone_id in official_ids:
                alias_targets.setdefault(alias, set()).add(zone_id)

    results = []
    ambiguity = Counter()
    for vendor in vendors:
        vendor_id = vendor["vendor_id"].strip()
        prior = existing.get(vendor_id)
        if prior and prior["review_status"] != "UNREVIEWED":
            preserved = dict(prior)
            preserved["candidate_zone_ids"] = json.loads(preserved.pop("candidate_zone_ids_json"))
            preserved["evidence_types"] = json.loads(preserved.pop("evidence_types_json"))
            preserved["preserved_review"] = True
            results.append(preserved)
            continue

        registry_row = registry.get(vendor_id, {})
        group = crosswalk.get(registry_row.get("location_group_id", ""), {})
        original = (vendor.get("current_vending_location_original") or "").strip()
        english = (vendor.get("current_vending_location_english") or group.get("business_location_english") or "").strip()
        division = (vendor.get("division") or registry_row.get("vendor_division") or "").strip()
        combined = f"{original} {english}"
        explicit_ids = sorted(set(re.findall(r"\b[A-Z]{2,4}(?:_[A-Z]+)?_\d{3}\b", combined.upper())) & official_ids)
        evidence = ["ORIGINAL_VENDING_LOCATION"] if original else []
        matched_zone_id = None
        matched_landmark = None
        status = "UNMATCHED"

        if len(explicit_ids) == 1:
            matched_zone_id = explicit_ids[0]
            status = "AUTO_MATCHED"
            evidence.extend(["EXPLICIT_OFFICIAL_ZONE_ID", "OFFICIAL_ZONE_REGISTRY"])
        elif group:
            reviewed_zone = group.get("reviewed_zone_id", "").strip()
            crosswalk_reviewed = group.get("review_status", "").strip().upper() in REVIEWED_CROSSWALK_STATUSES
            proposed = reviewed_zone if crosswalk_reviewed else group.get("proposed_zone_id", "").strip()
            alias = group.get("business_location_english") or group.get("business_location_normalized") or english
            alias_key = normalize_location(alias)
            division_consistent = bool(proposed in official_ids and division and
                                       group.get("division") == division and
                                       zone_by_id[proposed].get("division") == division)
            unique_alias = bool(alias_key and alias_targets.get(alias_key) == {proposed})
            strong_method = crosswalk_reviewed or group.get("match_method") in {"explicit_location_alias", "unique_source_phrase"}
            no_conflict = crosswalk_reviewed or not _candidate_ids(group.get("candidate_zone_ids"), official_ids)
            landmark_supported = proposed in official_ids and _distinctive_landmark_match(
                alias, zone_by_id[proposed].get("official_description", "")
            )
            status_supported = crosswalk_reviewed or group.get("match_status") == "text_association"
            if strong_method and status_supported and division_consistent and unique_alias and no_conflict and landmark_supported:
                matched_zone_id = proposed
                matched_landmark = alias
                status = "AUTO_MATCHED"
                evidence.extend((["REVIEWED_ALIAS"] if crosswalk_reviewed else []) + ["DISTINCTIVE_EXACT_LANDMARK", "UNIQUE_ALIAS", "DIVISION_CONSISTENT", "OFFICIAL_DESCRIPTION"])

        candidates = []
        if status != "AUTO_MATCHED":
            if explicit_ids:
                candidates.extend(explicit_ids)
                ambiguity["multiple explicit zone IDs"] += 1
            if group:
                for candidate in [group.get("reviewed_zone_id", "").strip(), group.get("proposed_zone_id", "").strip(),
                                  *_candidate_ids(group.get("candidate_zone_ids"), official_ids)]:
                    if candidate in official_ids and candidate not in candidates:
                        candidates.append(candidate)
                method = group.get("match_method") or "unknown"
                ambiguity[method] += 1
                evidence.append("CROSSWALK_SUPPORT_ONLY")
            for candidate in _rank_text_candidates(english or original, division, zones):
                if candidate not in candidates:
                    candidates.append(candidate)
            candidates = candidates[:3]
            if candidates:
                status = "REVIEW_REQUIRED"
                evidence.append("TEXT_SIMILARITY_CANDIDATES_ONLY")
            elif original or english:
                ambiguity["no defensible zone candidate"] += 1
            else:
                ambiguity["missing vending location"] += 1

        now = utc_now()
        results.append({
            "vendor_id": vendor_id,
            "matched_zone_id": matched_zone_id,
            "candidate_zone_ids": candidates,
            "original_location_text": original or None,
            "location_text_english": english or None,
            "recorded_division": division or None,
            "business_category": (vendor.get("business_category") or None),
            "match_status": status,
            "evidence_types": list(dict.fromkeys(evidence)),
            "matched_landmark": matched_landmark,
            "source_provenance": "historical_vendors + vendor_registry + location_zone_crosswalk + official_zones",
            "algorithm_version": ALGORITHM_VERSION,
            "review_status": "UNREVIEWED",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
            "created_at": prior["created_at"] if prior else now,
            "updated_at": now,
            "preserved_review": False,
        })

    if len(results) != len(vendors) or len({row["vendor_id"] for row in results}) != len(vendors):
        raise OperationalValidationError("Historical reconciliation did not preserve unique vendor coverage")
    for row in results:
        if row.get("matched_zone_id") and row["matched_zone_id"] not in official_ids:
            raise OperationalValidationError("Historical reconciliation produced an unknown zone ID")

    accepted = [row for row in results if row["review_status"] in ACCEPTED_REVIEW_STATUSES or
                (row["match_status"] == "AUTO_MATCHED" and row["review_status"] == "UNREVIEWED")]
    counts = Counter(row["match_status"] for row in results)
    division_counts = Counter(row.get("recorded_division") or "Not recorded" for row in accepted)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "results": results,
        "summary": {
            "processed": len(results),
            "auto_matched": counts["AUTO_MATCHED"],
            "review_required": counts["REVIEW_REQUIRED"],
            "unmatched": counts["UNMATCHED"],
            "accepted_zone_count": len({row["matched_zone_id"] for row in accepted if row.get("matched_zone_id")}),
            "accepted_by_division": dict(sorted(division_counts.items())),
            "preserved_reviewed": sum(bool(row.get("preserved_review")) for row in results),
            "top_ambiguity_patterns": ambiguity.most_common(10),
        },
    }


def persist_reconciliation(reconciliation: dict[str, Any], database_path=DATABASE_PATH) -> dict[str, int]:
    """Idempotently persist unreviewed results; human decisions always win."""
    initialize_schema(database_path)
    inserted = updated = unchanged = preserved = 0
    with transaction(database_path) as db:
        existing = {row["vendor_id"]: dict(row) for row in db.execute(
            "SELECT * FROM historical_vendor_zone_associations"
        )}
        for row in reconciliation["results"]:
            current = existing.get(row["vendor_id"])
            if current and current["review_status"] != "UNREVIEWED":
                preserved += 1
                continue
            values = {
                **{key: row.get(key) for key in (
                    "vendor_id", "matched_zone_id", "original_location_text", "location_text_english",
                    "recorded_division", "business_category", "match_status", "matched_landmark",
                    "source_provenance", "algorithm_version", "review_status", "reviewed_by",
                    "reviewed_at", "review_notes", "created_at", "updated_at",
                )},
                "candidate_zone_ids_json": json.dumps(row.get("candidate_zone_ids", []), ensure_ascii=False),
                "evidence_types_json": json.dumps(row.get("evidence_types", []), ensure_ascii=False),
            }
            if current:
                comparable_keys = set(values) - {"updated_at"}
                if all(current.get(key) == values[key] for key in comparable_keys):
                    unchanged += 1
                    continue
                assignments = ", ".join(f"{key} = :{key}" for key in values if key not in {"vendor_id", "created_at"})
                db.execute(f"UPDATE historical_vendor_zone_associations SET {assignments} WHERE vendor_id = :vendor_id", values)
                updated += 1
            else:
                columns = ", ".join(values)
                placeholders = ", ".join(f":{key}" for key in values)
                db.execute(f"INSERT INTO historical_vendor_zone_associations ({columns}) VALUES ({placeholders})", values)
                inserted += 1
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged, "preserved_reviewed": preserved}


def _decode_association(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    result["candidate_zone_ids"] = json.loads(result.pop("candidate_zone_ids_json"))
    result["evidence_types"] = json.loads(result.pop("evidence_types_json"))
    result["accepted"] = (
        result["review_status"] in ACCEPTED_REVIEW_STATUSES
        or (result["match_status"] == "AUTO_MATCHED" and result["review_status"] == "UNREVIEWED")
    )
    return result


def association_map(database_path=DATABASE_PATH) -> dict[str, dict[str, Any]]:
    initialize_schema(database_path)
    db = connect(database_path)
    try:
        return {row["vendor_id"]: _decode_association(row) for row in db.execute(
            "SELECT * FROM historical_vendor_zone_associations"
        )}
    finally:
        db.close()


def get_association(vendor_id: str, database_path=DATABASE_PATH) -> dict[str, Any] | None:
    initialize_schema(database_path)
    db = connect(database_path)
    try:
        return _decode_association(db.execute(
            "SELECT * FROM historical_vendor_zone_associations WHERE vendor_id = ?", (vendor_id,)
        ).fetchone())
    finally:
        db.close()


def zone_association_summary(database_path=DATABASE_PATH) -> dict[str, dict[str, Any]]:
    associations = association_map(database_path)
    summary: dict[str, dict[str, Any]] = {}
    for row in associations.values():
        if not row["accepted"] or not row.get("matched_zone_id"):
            continue
        zone = summary.setdefault(row["matched_zone_id"], {"historical_vendor_count": 0, "historical_business_categories": {}})
        zone["historical_vendor_count"] += 1
        category = row.get("business_category") or "unknown"
        zone["historical_business_categories"][category] = zone["historical_business_categories"].get(category, 0) + 1
    return summary


def review_association(vendor_id: str, decision: str, zone_id: str | None, reviewer: str,
                       notes: str | None = None, database_path=DATABASE_PATH) -> dict[str, Any]:
    decision = decision.strip().upper()
    if decision not in {"CONFIRM", "CHANGE", "REJECT"}:
        raise OperationalValidationError("decision must be CONFIRM, CHANGE, or REJECT")
    reviewer = reviewer.strip()
    if not reviewer:
        raise OperationalValidationError("Authenticated reviewer is required")
    now = utc_now()
    with transaction(database_path) as db:
        current = db.execute("SELECT * FROM historical_vendor_zone_associations WHERE vendor_id = ?", (vendor_id,)).fetchone()
        if current is None:
            raise OperationalNotFoundError("Historical vendor association not found")
        if decision != "REJECT":
            if not zone_id or db.execute("SELECT 1 FROM zone_live_status WHERE zone_id = ?", (zone_id,)).fetchone() is None:
                raise OperationalValidationError("A valid official zone_id is required")
            review_status = "CHANGED" if decision == "CHANGE" else "CONFIRMED"
            matched_zone_id = zone_id
            match_status = current["match_status"] if current["match_status"] != "UNMATCHED" else "REVIEW_REQUIRED"
        else:
            review_status, matched_zone_id, match_status = "REJECTED", None, "UNMATCHED"
        db.execute("""UPDATE historical_vendor_zone_associations
                      SET matched_zone_id=?, match_status=?, review_status=?, reviewed_by=?, reviewed_at=?, review_notes=?, updated_at=?
                      WHERE vendor_id=?""",
                   (matched_zone_id, match_status, review_status, reviewer, now, (notes or "").strip() or None, now, vendor_id))
        db.execute("""INSERT INTO admin_audit_log
                      (audit_id, action, entity_type, entity_id, performed_by, details_json, created_at)
                      VALUES (?, ?, 'historical_vendor_zone_association', ?, ?, ?, ?)""",
                   ("AUD_" + uuid.uuid4().hex, f"HISTORICAL_ASSOCIATION_{decision}", vendor_id, reviewer,
                    json.dumps({"before_zone_id": current["matched_zone_id"], "after_zone_id": matched_zone_id,
                                "previous_review_status": current["review_status"], "notes": (notes or "").strip() or None}), now))
        updated = db.execute("SELECT * FROM historical_vendor_zone_associations WHERE vendor_id = ?", (vendor_id,)).fetchone()
    return _decode_association(updated)


def associated_vendors_for_zone(zone_id: str, database_path=DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_schema(database_path)
    db = connect(database_path)
    try:
        rows = db.execute(
            """SELECT * FROM historical_vendor_zone_associations
               WHERE matched_zone_id = ?
                 AND ((match_status = 'AUTO_MATCHED' AND review_status = 'UNREVIEWED')
                      OR review_status IN ('CONFIRMED', 'CHANGED'))
               ORDER BY vendor_id""",
            (zone_id,),
        ).fetchall()
        return [_decode_association(row) for row in rows]
    finally:
        db.close()
