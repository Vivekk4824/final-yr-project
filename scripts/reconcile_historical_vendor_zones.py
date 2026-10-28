"""Dry-run or apply historical vendor-to-zone evidence reconciliation.

Default is staging only. Use --apply after reviewing the generated report.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.repositories.database import DATABASE_PATH, initialize_schema
from backend.services.historical_associations import persist_reconciliation, reconcile_historical_associations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist results after producing the dry-run report")
    parser.add_argument("--database", help="Optional SQLite path or PostgreSQL URL; defaults to configured database")
    args = parser.parse_args()
    database = args.database or DATABASE_PATH
    initialize_schema(database)
    reconciliation = reconcile_historical_associations(database)
    report_dir = ROOT / "reports" / "data_quality" / "historical_vendor_zones"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "summary.json").write_text(
        json.dumps(reconciliation["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = ["vendor_id", "matched_zone_id", "candidate_zone_ids", "recorded_division",
              "business_category", "match_status", "evidence_types", "matched_landmark",
              "source_provenance", "algorithm_version", "review_status", "preserved_review"]
    with (report_dir / "staging_results.csv").open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in reconciliation["results"]:
            output = {field: row.get(field) for field in fields}
            output["candidate_zone_ids"] = " | ".join(row.get("candidate_zone_ids", []))
            output["evidence_types"] = " | ".join(row.get("evidence_types", []))
            writer.writerow(output)
    persisted = persist_reconciliation(reconciliation, database) if args.apply else None
    print(json.dumps({"mode": "APPLY" if args.apply else "DRY_RUN", **reconciliation["summary"],
                      "persistence": persisted, "report_directory": str(report_dir)}, indent=2))


if __name__ == "__main__":
    main()
