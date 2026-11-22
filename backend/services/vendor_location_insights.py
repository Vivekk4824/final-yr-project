"""Vendor-facing aggregate-only competition and capacity context."""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from fastapi import HTTPException

from backend.repositories.database import DATABASE_PATH, OperationalNotFoundError, OperationalValidationError, connect
from backend.services.vendor_heatmap import vendor_heatmap_data
from backend.services.vendors import get_vendor_profile
from backend.services.zone_references import resolve_zone_locations

RADII_METRES = (100, 250, 500)
CELL_SIZE_METRES = 500
MIN_CELL_COUNT = 3


def _distance_metres(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude1, longitude1 = map(math.radians, first)
    latitude2, longitude2 = map(math.radians, second)
    latitude_delta = latitude2 - latitude1
    longitude_delta = longitude2 - longitude1
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude1) * math.cos(latitude2) * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * 6371008.8 * math.asin(math.sqrt(haversine))


def _valid_coordinates(coordinates) -> bool:
    return (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) == 2
        and all(type(value) in (float, int) and math.isfinite(float(value)) for value in coordinates)
        and -180 <= float(coordinates[0]) <= 180
        and -90 <= float(coordinates[1]) <= 90
    )


def _aggregate_cells(points: list[dict]) -> list[dict]:
    if not points:
        return []
    mean_latitude = math.radians(sum(point["latitude"] for point in points) / len(points))
    latitude_step = CELL_SIZE_METRES / 111_320
    longitude_step = CELL_SIZE_METRES / max(1, 111_320 * abs(math.cos(mean_latitude)))
    cells: dict[tuple[int, int], list[float]] = defaultdict(list)
    for point in points:
        row = math.floor(point["latitude"] / latitude_step)
        column = math.floor(point["longitude"] / longitude_step)
        cells[(row, column)].append(1)
    return [
        {
            "latitude": round((row + 0.5) * latitude_step, 5),
            "longitude": round((column + 0.5) * longitude_step, 5),
            "count": len(counts),
        }
        for (row, column), counts in sorted(cells.items())
        if len(counts) >= MIN_CELL_COUNT
    ]


def vendor_location_insights(
    vendor_id: str,
    zone_ids: list[str] | tuple[str, ...] = (),
    database_path: str | Path = DATABASE_PATH,
) -> dict:
    """Return category-filtered counts and coarse cells; never return vendor rows."""
    unique_zone_ids = list(dict.fromkeys(str(zone_id).strip() for zone_id in zone_ids if str(zone_id).strip()))
    if len(unique_zone_ids) > 3:
        raise OperationalValidationError("At most three recommended zones may be compared")

    profile = get_vendor_profile(vendor_id, database_path=database_path)
    if profile is None:
        raise OperationalNotFoundError("Vendor profile not found")
    category = str(profile.get("business_category") or "").strip()
    if not category:
        return {
            "business_category": None,
            "coverage": {"total_records": None, "mapped_records": None, "unmapped_records": None, "status": "NO_CATEGORY"},
            "heatmap": {"cells": [], "status": "NO_CATEGORY", "cell_size_metres": CELL_SIZE_METRES,
                        "minimum_cell_count": MIN_CELL_COUNT},
            "recommended_zones": [],
        }

    data = vendor_heatmap_data(business_category=category, database_path=database_path)
    own_ids = {vendor_id}
    if profile.get("application_vendor_id"):
        own_ids.add(str(profile["application_vendor_id"]))
    competition_points = [
        point for point in (data["competition_points"] or [])
        if str(point["vendor_id"]) not in own_ids
    ]
    coverage = {
        "total_records": data["mapping_summary"]["total_records"],
        "mapped_records": data["mapping_summary"]["mapped_records"],
        "unmapped_records": data["mapping_summary"]["unmapped_records"],
    }
    cells = _aggregate_cells(competition_points)
    if coverage["total_records"] == 0:
        coverage["status"] = "NO_DATA"
        heatmap_status = "NO_DATA"
    elif coverage["mapped_records"] == 0:
        coverage["status"] = "NO_MAPPED_COORDINATES"
        heatmap_status = "NO_MAPPED_COORDINATES"
    elif coverage["unmapped_records"]:
        coverage["status"] = "PARTIAL"
        heatmap_status = "AVAILABLE" if cells else "INSUFFICIENT_AGGREGATION"
    else:
        coverage["status"] = "COMPLETE"
        heatmap_status = "AVAILABLE" if cells else "INSUFFICIENT_AGGREGATION"

    recommended_zones = []
    if unique_zone_ids:
        placeholders = ",".join("?" for _ in unique_zone_ids)
        connection = connect(database_path)
        try:
            zone_rows = {
                row["zone_id"]: dict(row)
                for row in connection.execute(
                    f"""SELECT zone_id, official_capacity, current_vendor_count, available_capacity
                        FROM zone_live_status WHERE zone_id IN ({placeholders})""",
                    tuple(unique_zone_ids),
                )
            }
        finally:
            connection.close()

        missing_ids = [zone_id for zone_id in unique_zone_ids if zone_id not in zone_rows]
        if missing_ids:
            raise OperationalValidationError("A recommended zone is not available in the operational zone catalogue")

        try:
            zone_locations = resolve_zone_locations(database_path)
        except HTTPException as error:
            if error.status_code != 503:
                raise
            zone_locations = {}
            location_data_available = False
        else:
            location_data_available = True

        points = competition_points
        for zone_id in unique_zone_ids:
            location = zone_locations.get(zone_id, {})
            coordinates = location.get("coordinates")
            has_location = location_data_available and _valid_coordinates(coordinates)
            if not has_location or coverage["mapped_records"] == 0:
                counts = {f"{radius}m": None for radius in RADII_METRES}
            else:
                center = (float(coordinates[1]), float(coordinates[0]))
                counts = {
                    f"{radius}m": sum(
                        _distance_metres(center, (point["latitude"], point["longitude"])) <= radius
                        for point in points
                    )
                    for radius in RADII_METRES
                }
            zone_row = zone_rows[zone_id]
            recommended_zones.append({
                "zone_id": zone_id,
                "coordinates": coordinates if has_location else None,
                "location_source": location.get("location_source") if has_location else None,
                "nearby_same_category": counts,
                "counts_status": (
                    "AVAILABLE" if has_location and coverage["mapped_records"] > 0
                    else "NO_MAPPED_COORDINATES" if coverage["mapped_records"] == 0
                    else "LOCATION_UNAVAILABLE"
                ),
                "available_capacity": zone_row["available_capacity"],
                "official_capacity": zone_row["official_capacity"],
                "current_vendor_count": zone_row["current_vendor_count"],
            })

    return {
        "business_category": category,
        "coverage": coverage,
        "heatmap": {
            "cells": cells,
            "status": heatmap_status,
            "cell_size_metres": CELL_SIZE_METRES,
            "minimum_cell_count": MIN_CELL_COUNT,
        },
        "recommended_zones": recommended_zones,
        "notice": (
            "Counts use active operational and allocated vendors with recorded coordinates in your registered "
            "business category. Heatmap cells are 500 m aggregates and cells with fewer than three records are hidden. "
            "A map location is a reference point, not an official zone boundary."
        ),
    }
