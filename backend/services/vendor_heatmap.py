"""Admin-only, read-only vendor-location density evidence."""
from __future__ import annotations

import math
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.errors import ShapelyError
from shapely.geometry import shape

from backend.repositories.database import DATABASE_PATH, connect
from backend.services.vendors import get_vendor_profiles


def _text(value) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def _valid_coordinate(latitude, longitude) -> bool:
    return (
        type(latitude) in (float, int)
        and type(longitude) in (float, int)
        and math.isfinite(float(latitude))
        and math.isfinite(float(longitude))
        and -90 <= float(latitude) <= 90
        and -180 <= float(longitude) <= 180
    )


def _location(row: dict) -> tuple[str, str, str]:
    if row.get("zone_id"):
        value = _text(row["zone_id"])
        return f"zone:{value}", f"Zone {value}", "zone"
    if row.get("preferred_locality"):
        value = _text(row["preferred_locality"])
        return f"locality:{value}", value, "locality"
    return "unrecorded", "Zone/locality not recorded", "unrecorded"


def _slot_coordinate(geometry_json) -> tuple[float, float] | None:
    """Read the centre of an assigned WGS84 slot without changing its geometry."""
    if not geometry_json:
        return None
    try:
        geometry = shape(json.loads(geometry_json))
        centre = geometry.centroid
        latitude, longitude = float(centre.y), float(centre.x)
    except (TypeError, ValueError, json.JSONDecodeError, ShapelyError):
        return None
    return (latitude, longitude) if _valid_coordinate(latitude, longitude) else None


def _extent_density(points: list[dict]) -> tuple[float | None, float | None]:
    """Return bounding-box area and recorded-pin density, never legal-zone area."""
    if len(points) < 2:
        return None, None
    latitudes = [point["latitude"] for point in points]
    longitudes = [point["longitude"] for point in points]
    mean_latitude = sum(latitudes) / len(latitudes)
    north_south_km = (max(latitudes) - min(latitudes)) * 111.32
    east_west_km = (
        (max(longitudes) - min(longitudes))
        * 111.32
        * abs(math.cos(math.radians(mean_latitude)))
    )
    area = north_south_km * east_west_km
    # Near-identical pins do not provide a meaningful spatial-area denominator.
    if not math.isfinite(area) or area < 0.01:
        return None, None
    return round(area, 3), round(len(points) / area, 2)


def _statistics(points: list[dict]) -> dict:
    area, density = _extent_density(points)
    return {
        "total_vendors": len(points),
        "unique_coordinates": len({(point["latitude"], point["longitude"]) for point in points}),
        "category_distribution": dict(sorted(Counter(point["business_category"] for point in points).items())),
        "coordinate_extent_km2": area,
        "vendor_density_per_km2": density,
        "density_basis": "bounding_box_of_recorded_working_pins",
    }


def vendor_heatmap_data(
    *,
    business_category: str = "",
    location_key: str = "",
    database_path: str | Path = DATABASE_PATH,
) -> dict:
    """Return de-identified, valid operational vendor pins and transparent quality counts."""
    connection = connect(database_path)
    try:
        operational_rows = [dict(row.items()) for row in connection.execute(
            """SELECT v.vendor_id, v.application_vendor_id, v.business_category,
                      v.preferred_division, v.preferred_locality,
                      v.preferred_latitude, v.preferred_longitude,
                      a.zone_id, NULL AS slot_zone_id,
                      NULL AS slot_geometry_json
               FROM operational_vendors AS v
               LEFT JOIN allocations AS a
                 ON a.vendor_id = v.vendor_id AND a.status = 'ACTIVE'
               WHERE v.status = 'ACTIVE'
               ORDER BY v.vendor_id"""
        )]
        assigned_rows = [dict(row.items()) for row in connection.execute(
            """SELECT a.vendor_id, v.application_vendor_id,
                      COALESCE(v.business_category, r.business_category) AS business_category,
                      v.preferred_division, v.preferred_locality,
                      v.preferred_latitude, v.preferred_longitude,
                      a.zone_id, s.zone_id AS slot_zone_id,
                      s.geometry_json AS slot_geometry_json
               FROM allocations AS a
               JOIN pilot_slots AS s
                 ON s.assigned_vendor_id = a.vendor_id
                AND s.zone_id = a.zone_id AND s.slot_id = a.slot_id
                AND s.is_deleted = 0 AND s.geometry_crs = 'EPSG:4326'
               LEFT JOIN operational_vendors AS v ON v.vendor_id = a.vendor_id
               LEFT JOIN allocation_requests AS r ON r.request_id = a.request_id
               WHERE a.status = 'ACTIVE'
               ORDER BY a.vendor_id"""
        )]
        municipal_zone_ids = [row["zone_id"] for row in connection.execute(
            "SELECT zone_id FROM zone_live_status ORDER BY zone_id"
        )]
    finally:
        connection.close()

    rows_by_vendor = {row["vendor_id"]: row for row in operational_rows}
    assigned_vendor_ids = set()
    for assigned in assigned_rows:
        assigned_vendor_ids.add(assigned["vendor_id"])
        existing = rows_by_vendor.get(assigned["vendor_id"], {})
        rows_by_vendor[assigned["vendor_id"]] = {
            **assigned,
            **{key: value for key, value in existing.items() if value is not None},
            "zone_id": assigned["zone_id"],
            "slot_zone_id": assigned["slot_zone_id"],
            "slot_geometry_json": assigned["slot_geometry_json"],
        }
    rows = list(rows_by_vendor.values())
    profiles = get_vendor_profiles([row["vendor_id"] for row in rows], database_path=database_path)
    for row in rows:
        profile = profiles.get(row["vendor_id"], {})
        for field in ("application_vendor_id", "business_category", "preferred_division", "preferred_locality",
                      "preferred_latitude", "preferred_longitude"):
            if row.get(field) is None and profile.get(field) is not None:
                row[field] = profile[field]

    quality = {
        "active_operational_records": len(operational_rows),
        "active_vendor_records": len(rows),
        "assigned_slot_records": len(assigned_vendor_ids),
        "assigned_slot_only_records": len(assigned_vendor_ids - {row["vendor_id"] for row in operational_rows}),
        "valid_coordinate_records": 0,
        "missing_coordinate_records": 0,
        "invalid_coordinate_records": 0,
        "profile_coordinate_records": 0,
        "assigned_slot_coordinate_records": 0,
        "incomplete_category_records": 0,
        "duplicate_coordinate_groups": 0,
        "records_at_duplicate_coordinates": 0,
    }
    points: list[dict] = []
    mapping_records: list[dict] = []
    all_category_counts: Counter[str] = Counter()
    for row in rows:
        category = _text(row.get("business_category")) or "unknown"
        all_category_counts[category] += 1
        if category == "unknown":
            quality["incomplete_category_records"] += 1
        slot_coordinate = _slot_coordinate(row.get("slot_geometry_json"))
        latitude, longitude = row.get("preferred_latitude"), row.get("preferred_longitude")
        coordinate_source = None
        mapping_issue = None
        if slot_coordinate:
            latitude, longitude = slot_coordinate
            row["zone_id"] = row.get("slot_zone_id") or row.get("zone_id")
            coordinate_source = "assigned_slot"
            quality["assigned_slot_coordinate_records"] += 1
        elif latitude is None or longitude is None:
            quality["missing_coordinate_records"] += 1
            mapping_issue = "missing_coordinates"
        elif not _valid_coordinate(latitude, longitude):
            quality["invalid_coordinate_records"] += 1
            mapping_issue = "invalid_coordinates"
        else:
            coordinate_source = "vendor_profile"
            quality["profile_coordinate_records"] += 1
        key, label, kind = _location(row)
        vendor_id = _text(row.get("application_vendor_id")) or row["vendor_id"]
        mapping_records.append({
            "vendor_id": vendor_id,
            "business_category": category,
            "zone_id": _text(row.get("zone_id")),
            "locality": _text(row.get("preferred_locality")),
            "location_key": key,
            "location_label": label,
            "mapping_status": "mapped" if coordinate_source else "unmapped",
            "coordinate_source": coordinate_source,
            "mapping_issue": mapping_issue,
        })
        if not coordinate_source:
            continue
        points.append({
            "vendor_id": vendor_id,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "business_category": category,
            "zone_id": _text(row.get("zone_id")),
            "locality": _text(row.get("preferred_locality")),
            "division": _text(row.get("preferred_division")),
            "location_key": key,
            "location_label": label,
            "location_type": kind,
            "coordinate_source": coordinate_source,
        })

    quality["valid_coordinate_records"] = len(points)
    coordinate_counts = Counter((point["latitude"], point["longitude"]) for point in points)
    duplicates = [count for count in coordinate_counts.values() if count > 1]
    quality["duplicate_coordinate_groups"] = len(duplicates)
    quality["records_at_duplicate_coordinates"] = sum(duplicates)

    located_category_counts = Counter(point["business_category"] for point in points)
    categories = [{
        "value": category,
        "count": located_category_counts.get(category, 0),
        "located_count": located_category_counts.get(category, 0),
        "total_count": total_count,
        "unmapped_count": total_count - located_category_counts.get(category, 0),
    } for category, total_count in sorted(all_category_counts.items())]
    location_counts: dict[tuple[str, str, str], int] = Counter(
        (point["location_key"], point["location_label"], point["location_type"])
        for point in points
    )
    location_record_counts = Counter(record["location_key"] for record in mapping_records)
    location_catalog = {
        (f"zone:{zone_id}", f"Zone {zone_id}", "zone")
        for zone_id in municipal_zone_ids
    }
    location_catalog.update(
        (f"locality:{locality}", locality, "locality")
        for locality in {_text(row.get("preferred_locality")) for row in rows}
        if locality
    )
    location_catalog.update(location_counts)
    locations = [
        {"value": key, "label": label, "type": kind,
         "count": location_counts.get((key, label, kind), 0),
         "mapped_count": location_counts.get((key, label, kind), 0),
         "total_count": location_record_counts.get(key, 0),
         "unmapped_count": location_record_counts.get(key, 0) - location_counts.get((key, label, kind), 0)}
        for key, label, kind in sorted(
            location_catalog, key=lambda item: (item[2], item[1].casefold())
        )
    ]

    selected_category = business_category.strip()
    selected_location = location_key.strip()
    known_categories = {item["value"] for item in categories}
    known_locations = {item["value"] for item in locations}
    if selected_category and selected_category not in known_categories:
        points = []
        mapping_records = []
    elif selected_category:
        points = [point for point in points if point["business_category"] == selected_category]
        mapping_records = [record for record in mapping_records if record["business_category"] == selected_category]
    competition_points = None
    if selected_category:
        # Competition remains radius-based across the city; a display locality
        # must not hide a nearby same-category pin just across its label boundary.
        competition_points = [{
            "vendor_id": point["vendor_id"],
            "latitude": point["latitude"],
            "longitude": point["longitude"],
            "business_category": point["business_category"],
        } for point in points]
    if selected_location and selected_location not in known_locations:
        points = []
        mapping_records = []
    elif selected_location:
        points = [point for point in points if point["location_key"] == selected_location]
        mapping_records = [record for record in mapping_records if record["location_key"] == selected_location]

    mapped_record_count = sum(record["mapping_status"] == "mapped" for record in mapping_records)
    mapping_summary = {
        "total_records": len(mapping_records),
        "mapped_records": mapped_record_count,
        "unmapped_records": len(mapping_records) - mapped_record_count,
        "mapping_coverage_percent": round(mapped_record_count * 100 / len(mapping_records), 1)
        if mapping_records else 0,
    }

    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for point in points:
        grouped[(point["location_key"], point["location_label"], point["location_type"])].append(point)
    location_statistics = []
    for (key, label, kind), group in grouped.items():
        location_statistics.append({
            "location_key": key,
            "location_label": label,
            "location_type": kind,
            **_statistics(group),
        })
    location_statistics.sort(key=lambda item: (-item["total_vendors"], item["location_label"].casefold()))

    return {
        "points": points,
        "mapping_records": mapping_records,
        "mapping_summary": mapping_summary,
        "competition_points": competition_points,
        "summary": _statistics(points),
        "location_statistics": location_statistics,
        "filters": {"categories": categories, "locations": locations},
        "data_quality": quality,
        "selected_filters": {
            "business_category": selected_category or None,
            "location_key": selected_location or None,
        },
        "location_semantics": (
            "Coordinates come from assigned WGS84 vending slots when available, otherwise from vendor-provided "
            "preferred working-location pins. Zone filters come from the municipal zone catalogue; locality "
            "labels are profile-entered. Vendors without either coordinate source are not placed on the map."
        ),
        "density_notice": (
            "Density uses the bounding box of recorded pins, not an official municipal zone area. "
            "Lower recorded density does not establish unmet demand or an underserved area."
        ),
    }
