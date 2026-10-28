"""One-time controlled import of reliable historical vendor allocations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Importing project config loads the root .env with OS values taking precedence.
from backend.core import config as _project_config  # noqa: F401

from backend.repositories.database import DATABASE_PATH, database_backend
from backend.services.legacy_allocation_import import (
    apply_legacy_import,
    build_legacy_import_plan,
)


REPORT_PATH = PROJECT_ROOT / "reports" / "migrations" / "existing_vendor_allocation_import.json"


def _print_report(report: dict) -> None:
    skipped = report["skipped_counts"]
    print(f"Mode: {report['mode']}")
    print(f"Database backend: {report['database_backend']}")
    print(f"Total historical vendors: {report['total_historical_vendors']}")
    print(f"Reliable mapped vendors: {report['reliable_mapped_vendors']}")
    print(f"Already active: {report['already_active']}")
    print(f"Existing active allocation wins: {report['existing_active_allocation_wins']}")
    print(f"Import candidates: {report['candidate_count']}")
    print(f"Imported: {report['imported_count']}")
    for reason in (
        "needs_review", "missing_mapping", "invalid_zone", "restricted_zone",
        "no_vending_zone", "invalid_zone_type", "already_active", "released_history",
    ):
        print(f"Excluded - {reason}: {skipped.get(reason, 0)}")
    print(f"Zones with projected/current capacity overflow: {len(report['capacity_overflow_zones'])}")
    print(f"Zones with unknown capacity: {len(report['unknown_capacity_zones'])}")
    print("Top affected zones:")
    for zone in report["top_affected_zones"][:10]:
        capacity = "unknown" if zone["official_capacity"] is None else zone["official_capacity"]
        print(
            f"  {zone['zone_id']}: +{zone['candidate_imports']} imports, "
            f"projected occupancy {zone['projected_active_occupancy']}, capacity {capacity}, "
            f"overflow {zone['overflow_count']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import reliable historical mappings as LEGACY_IMPORT ACTIVE allocations."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan only; make no writes (default).")
    mode.add_argument("--apply", action="store_true", help="Apply atomically to configured PostgreSQL.")
    args = parser.parse_args()

    if args.apply:
        if database_backend(DATABASE_PATH) != "postgresql":
            parser.error("--apply is restricted to the configured PostgreSQL database; SQLite backup is untouched")
        report = apply_legacy_import(DATABASE_PATH)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = REPORT_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(REPORT_PATH)
        _print_report(report)
        print(f"Migration report: {REPORT_PATH}")
        return 0

    report = build_legacy_import_plan(DATABASE_PATH)
    _print_report(report)
    print("Dry-run only: no schema, allocation, live-status, audit, or report-file writes were made.")
    print("Run with --apply only after reviewing these counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

