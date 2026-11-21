"""Generate deterministic synthetic zone requirements for demonstrations only.

The output is not municipal evidence and must be replaced before operational use.
"""
from __future__ import annotations

import csv
import hashlib
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "nmc" / "official_zones.csv"
OUTPUT = ROOT / "data" / "demo" / "zone_requirement_profiles.csv"
PERIODS = ("MORNING", "DAYTIME", "EVENING")


def rng_for(zone_id: str) -> random.Random:
    seed = int.from_bytes(
        hashlib.sha256(f"vendor-map-demo:{zone_id}".encode()).digest()[:8],
        "big",
    )
    return random.Random(seed)


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8-sig") as source:
        zones = list(csv.DictReader(source))
    rows = []
    for zone in zones:
        randomizer = rng_for(zone["zone_id"])
        period_count = randomizer.randint(1, len(PERIODS))
        allowed = sorted(randomizer.sample(PERIODS, period_count), key=PERIODS.index)
        rows.append({
            "zone_id": zone["zone_id"],
            "allowed_operating_periods": "|".join(allowed),
            "available_stall_space_sqm": round(randomizer.uniform(4.0, 24.0), 1),
            "monthly_fee": int(round(randomizer.uniform(800.0, 8000.0) / 100.0) * 100),
            "data_source": "SYNTHETIC_DEMO_NOT_MUNICIPAL_DATA",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} deterministic demo profiles to {OUTPUT}")


if __name__ == "__main__":
    main()
