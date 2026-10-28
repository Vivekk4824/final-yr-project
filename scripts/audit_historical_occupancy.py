"""Print a privacy-safe, read-only historical occupancy reconciliation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.repositories.database import DATABASE_PATH
from backend.services.historical_occupancy_reconciliation import audit_historical_occupancy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", help="Optional official zone_id filter")
    args = parser.parse_args()
    result = audit_historical_occupancy(DATABASE_PATH, zone_id=args.zone)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
