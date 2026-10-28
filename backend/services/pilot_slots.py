"""Isolated research schematic; coordinates are local metres, never WGS84 slots."""
from __future__ import annotations
from backend.core.data_paths import dataset_path

import csv
import json
import math
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from pyproj import Geod
from shapely.geometry import Point, Polygon, box, mapping, shape
from shapely.validation import explain_validity
from sqlalchemy.exc import IntegrityError

import backend.geo.pilot_geometry as gis

from backend.repositories.database import ROOT, DATABASE_PATH, OFFICIAL_ZONES_PATH, connect, for_update, transaction, utc_now, release_allocation_in_transaction, OperationalConflictError, OperationalNotFoundError, OperationalValidationError

PILOT_ZONE_ID = "NN_F_013"
INTERACTIVE_DRAW_ZONE_ID = "PAN_F_031"
PILOT_ZONES = {PILOT_ZONE_ID: 10, **gis.IMPORTED_ZONE_CAPACITIES, INTERACTIVE_DRAW_ZONE_ID: 30}
STATUSES = ("AVAILABLE", "RESERVED", "OCCUPIED", "BLOCKED")
SURVEY_POINTS = [
    {"id": "A", "latitude": 19.975052, "longitude": 73.771769},
    {"id": "B", "latitude": 19.973551, "longitude": 73.772989},
    {"id": "C", "latitude": 19.973372, "longitude": 73.773213},
]


def pilot_evidence(zone_id=PILOT_ZONE_ID):
    with OFFICIAL_ZONES_PATH.open(encoding="utf-8-sig", newline="") as source:
        records = [row for row in csv.DictReader(source)
                   if row["zone_id"] in ((zone_id, "NV_064", "NV_069") if zone_id == PILOT_ZONE_ID else (zone_id,))]
    path = dataset_path("analytical_geometry")
    features = []
    if path.exists():
        features = [f for f in json.loads(path.read_text(encoding="utf-8"))["features"]
                    if f["properties"].get("zone_id") in ((zone_id, "NV_064", "NV_069") if zone_id == PILOT_ZONE_ID else (zone_id,))]
    reference = next((f for f in features if f["properties"]["zone_id"] == zone_id), None)
    points = [dict(point) for point in SURVEY_POINTS] if zone_id == PILOT_ZONE_ID else []
    if reference and reference.get("geometry"):
        geometry = shape(reference["geometry"])
        center = geometry.centroid
        for point in points:
            point["inside_analytical_reference"] = geometry.covers(Point(point["longitude"], point["latitude"]))
            point["distance_to_reference_m"] = round(Geod(ellps="WGS84").inv(
                point["longitude"], point["latitude"], center.x, center.y)[2], 1)
    return {"official_records": records, "analytical_references": features,
            "survey_points": points, "spatial_match": "UNVERIFIED",
            "verified_boundary": None, "measured_usable_width": None,
            "warning": "Shared analytical references are not official boundaries. Survey point zone membership is unverified. The connecting line is survey context, not a measured vending strip."}


def generate_layout(*, width=2.0, depth=2.0, spacing=0.5, clearance=1.2, count=10, capacity=10):
    """Generate a single row of rectangles and a corridor in a local metric plane."""
    values = (width, depth, spacing, clearance)
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in values):
        raise OperationalValidationError("Dimensions must be finite numbers")
    if width <= 0 or depth <= 0 or spacing < 0 or clearance <= 0:
        raise OperationalValidationError("Dimensions and clearance must be positive; spacing cannot be negative")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (count, capacity)) or not 1 <= count <= min(capacity, 10):
        raise OperationalValidationError("Slot count must be between 1 and the listed capacity, with a pilot maximum of 10")
    slots = []
    for index in range(count):
        x = index * (width + spacing)
        slots.append({"slot_id": f"S{index + 1:03d}", "zone_id": PILOT_ZONE_ID,
                      "width_m": width, "depth_m": depth, "x_m": x, "y_m": clearance,
                      "schematic_geometry": mapping(box(x, clearance, x + width, clearance + depth)),
                      "status": "AVAILABLE", "assigned_vendor_id": None,
                      "validation_state": "ILLUSTRATIVE_UNVERIFIED"})
    return {"zone_id": PILOT_ZONE_ID, "coordinate_system": "LOCAL_SCHEMATIC_METRES",
            "georeferenced": False, "validation_state": "ILLUSTRATIVE_UNVERIFIED",
            "width_m": width, "depth_m": depth, "spacing_m": spacing,
            "clearance_m": clearance, "length_m": count * width + (count - 1) * spacing,
            "orientation": "CONCEPTUAL", "slots": slots}


def initialize_demo(database_path=DATABASE_PATH, zone_id=PILOT_ZONE_ID):
    validate_zone(zone_id)
    if zone_id == INTERACTIVE_DRAW_ZONE_ID:
        return initialize_drawn_zone(database_path, zone_id)
    if zone_id not in PILOT_ZONES:
        return initialize_drawn_zone(database_path, zone_id)
    if zone_id != PILOT_ZONE_ID:
        return initialize_imported(database_path, zone_id)
    evidence = pilot_evidence()
    official = next(r for r in evidence["official_records"] if r["zone_id"] == zone_id)
    layout = generate_layout(capacity=int(official["capacity"]), count=min(10, int(official["capacity"])))
    metadata = {k: v for k, v in layout.items() if k != "slots"}
    with transaction(database_path, immediate=True) as db:
        current = db.execute("SELECT metadata_json FROM pilot_slot_layouts WHERE zone_id = ?", (zone_id,)).fetchone()
        if current and json.loads(current["metadata_json"]).get("georeferenced"):
            return get_layout(database_path, zone_id)
        db.execute("INSERT INTO pilot_slot_layouts(zone_id, metadata_json, created_at) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                   (zone_id, json.dumps(metadata), utc_now()))
        for slot in layout["slots"]:
            db.execute("""INSERT INTO pilot_slots
                (zone_id, slot_id, width_m, depth_m, x_m, y_m, geometry_json, status, validation_state, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'AVAILABLE', 'ILLUSTRATIVE_UNVERIFIED', ?) ON CONFLICT DO NOTHING""",
                (zone_id, slot["slot_id"], slot["width_m"], slot["depth_m"], slot["x_m"],
                 slot["y_m"], json.dumps(slot["schematic_geometry"]), utc_now()))
    return get_layout(database_path, zone_id)


def _slot(row):
    result = dict(row)
    geometry = json.loads(result.pop("geometry_json"))
    if result.get("geometry_crs") == "EPSG:4326":
        result["geometry"] = geometry
        result["pose"] = gis.slot_pose(geometry)
        result["geometry_verification_status"] = "PROVISIONAL_NOT_SURVEYED"
        result["validation_state"] = "PROVISIONAL_NOT_SURVEYED"
    else:
        result["schematic_geometry"] = geometry
    return result


def get_layout(database_path=DATABASE_PATH, zone_id=PILOT_ZONE_ID):
    validate_zone(zone_id)
    db = connect(database_path)
    try:
        row = db.execute("SELECT * FROM pilot_slot_layouts WHERE zone_id = ?", (zone_id,)).fetchone()
        if not row:
            raise OperationalNotFoundError("Pilot has not been initialized by an administrator")
        layout = json.loads(row["metadata_json"])
        layout["slots"] = [_slot(r) for r in db.execute(
            "SELECT * FROM pilot_slots WHERE zone_id = ? AND is_deleted = 0 ORDER BY slot_id", (zone_id,))]
        layout["evidence"] = pilot_evidence(zone_id)
        if not layout.get("georeferenced"):
            layout["boundaries"] = gis.load_boundaries()
        layout.setdefault("revision", "LEGACY")
        layout.setdefault("operational_enabled", zone_id == PILOT_ZONE_ID)
        categories = {r["vendor_id"]: r["business_category"] for r in db.execute(
            "SELECT a.vendor_id,r.business_category FROM allocations a JOIN allocation_requests r ON r.request_id=a.request_id WHERE a.zone_id=? AND a.status='ACTIVE' AND r.status='APPROVED' AND r.vendor_id=a.vendor_id AND r.zone_id=a.zone_id", (zone_id,))}
        for slot in layout["slots"]:
            slot["public_business_category"] = categories.get(slot["assigned_vendor_id"])
        official = next((r for r in layout["evidence"]["official_records"] if r["zone_id"] == zone_id), {})
        active_allocations = db.execute(
            "SELECT COUNT(*) AS total FROM allocations WHERE zone_id=? AND status='ACTIVE'", (zone_id,)
        ).fetchone()["total"]
        mapped_allocations = sum(bool(s.get("assigned_vendor_id")) for s in layout["slots"])
        authoritative_available = None if not official.get("capacity") else max(0, int(float(official["capacity"])) - active_allocations)
        raw_available_slots = sum(s["status"] == "AVAILABLE" for s in layout["slots"])
        layout["summary"] = {"listed_capacity": int(float(official["capacity"])) if official.get("capacity") else None,
            "mapped_slots": len(layout["slots"]), "occupied_slots": sum(s["status"] == "OCCUPIED" for s in layout["slots"]),
            "reserved_slots": sum(s["status"] == "RESERVED" for s in layout["slots"]),
            "available_slots": raw_available_slots,
            "active_allocations": active_allocations,
            "unmapped_active_allocations": max(0, active_allocations - mapped_allocations),
            "remaining_uncreated_capacity": None if authoritative_available is None else max(0, int(float(official["capacity"])) - len(layout["slots"])),
            "requestable_slots": raw_available_slots if authoritative_available is None else min(raw_available_slots, authoritative_available)}
        layout["pilot_zones"] = [{"zone_id": z, "mapped_capacity": capacity} for z,capacity in PILOT_ZONES.items()]
        return layout
    finally:
        db.close()


def update_slot(slot_id, status, vendor_id, *, actor, expected_updated_at, database_path=DATABASE_PATH, zone_id=PILOT_ZONE_ID):
    validate_zone(zone_id)
    if zone_id != PILOT_ZONE_ID and (vendor_id or status in ("RESERVED", "OCCUPIED")) and not get_layout(database_path, zone_id).get("operational_enabled"):
        raise OperationalValidationError("Administrator review and activation are required before assignment or occupancy")
    if status not in STATUSES:
        raise OperationalValidationError("Unknown slot status")
    if vendor_id is not None and (not vendor_id.strip() or status not in ("RESERVED", "OCCUPIED")):
        raise OperationalValidationError("Vendor assignment requires RESERVED or OCCUPIED status")
    try:
        with transaction(database_path, immediate=True) as db:
            current = db.execute(
                "SELECT * FROM pilot_slots WHERE zone_id = ? AND slot_id = ?" + for_update(db),
                (zone_id, slot_id),
            ).fetchone()
            if not current or current["is_deleted"]:
                raise OperationalNotFoundError("Unknown pilot slot")
            if current["updated_at"] != expected_updated_at:
                raise OperationalConflictError("Slot changed since it was loaded. Refresh before saving.")
            if current["assigned_vendor_id"] and vendor_id and current["assigned_vendor_id"] != vendor_id:
                raise OperationalConflictError("Release the current demo assignment before assigning another vendor")
            if vendor_id:
                if not current["assigned_vendor_id"] and current["status"] != "AVAILABLE":
                    raise OperationalConflictError("A new vendor assignment requires an AVAILABLE slot")
                approved = db.execute("""SELECT a.allocation_id FROM allocations a
                    WHERE a.vendor_id = ? AND a.zone_id = ? AND a.status = 'ACTIVE'
                    AND (a.allocation_source='LEGACY_IMPORT' OR EXISTS (
                        SELECT 1 FROM allocation_requests r WHERE r.request_id=a.request_id
                        AND r.status='APPROVED' AND r.vendor_id=a.vendor_id AND r.zone_id=a.zone_id))""",
                    (vendor_id, zone_id)).fetchone()
                if not approved:
                    raise OperationalValidationError("Vendor needs a current approved allocation for the pilot zone")
                db.execute(
                    "UPDATE allocations SET slot_id = ?, updated_at = ? WHERE allocation_id = ? AND status = 'ACTIVE'",
                    (slot_id, datetime.now(timezone.utc).isoformat(timespec="microseconds"), approved["allocation_id"]),
                )
            timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            released_allocation_id = None
            detached_allocation_id = None
            allocation = None
            if not vendor_id and (current["assigned_vendor_id"] or current["active_allocation_id"]):
                if current["active_allocation_id"]:
                    allocation = db.execute(
                        """SELECT * FROM allocations WHERE allocation_id = ?
                           AND zone_id = ? AND status = 'ACTIVE'""",
                        (current["active_allocation_id"], zone_id),
                    ).fetchone()
                elif current["assigned_vendor_id"]:
                    allocation = db.execute(
                        """SELECT * FROM allocations
                           WHERE vendor_id = ? AND zone_id = ? AND status = 'ACTIVE'
                           LIMIT 1""",
                        (current["assigned_vendor_id"], zone_id),
                    ).fetchone()
            if not vendor_id and allocation is None:
                allocation = db.execute(
                    """SELECT * FROM allocations WHERE zone_id = ? AND slot_id = ?
                       AND status = 'ACTIVE'""",
                    (zone_id, slot_id),
                ).fetchone()
            if not vendor_id and allocation is None and status in ("AVAILABLE", "BLOCKED"):
                history = db.execute(
                    """SELECT before_json, after_json FROM pilot_slot_events
                       WHERE zone_id = ? AND slot_id = ? ORDER BY event_id DESC""",
                    (zone_id, slot_id),
                ).fetchall()
                for event in history:
                    before = json.loads(event["before_json"] or "{}")
                    after = json.loads(event["after_json"] or "{}")
                    if after.get("status") != "AVAILABLE" or after.get("assigned_vendor_id") is not None:
                        continue
                    previous_vendor_id = before.get("assigned_vendor_id")
                    previous_allocation_id = before.get("active_allocation_id")
                    if previous_allocation_id:
                        allocation = db.execute(
                            """SELECT * FROM allocations WHERE allocation_id = ?
                               AND zone_id = ? AND status = 'ACTIVE'""",
                            (previous_allocation_id, zone_id),
                        ).fetchone()
                    elif previous_vendor_id:
                        allocation = db.execute(
                            """SELECT * FROM allocations WHERE vendor_id = ? AND zone_id = ?
                               AND status = 'ACTIVE'
                               LIMIT 1""",
                            (previous_vendor_id, zone_id),
                        ).fetchone()
                    break
            if not vendor_id and allocation is not None:
                if status == "AVAILABLE":
                    db.execute(
                        """UPDATE allocations SET slot_id = NULL, updated_at = ?
                           WHERE allocation_id = ? AND status = 'ACTIVE'""",
                        (timestamp, allocation["allocation_id"]),
                    )
                    detached_allocation_id = allocation["allocation_id"]
                else:
                    release_allocation_in_transaction(db, allocation["allocation_id"], actor, timestamp)
                    released_allocation_id = allocation["allocation_id"]
            db.execute("""UPDATE pilot_slots SET status = ?, assigned_vendor_id = ?,
                active_allocation_id = ?, pending_request_id = NULL, updated_at = ?
                WHERE zone_id = ? AND slot_id = ?""",
                (status, vendor_id, approved["allocation_id"] if vendor_id else None,
                 timestamp, zone_id, slot_id))
            db.execute("""INSERT INTO pilot_slot_events(zone_id, slot_id, actor, before_json, after_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""", (zone_id, slot_id, actor, json.dumps(dict(current)),
                json.dumps({"status": status, "assigned_vendor_id": vendor_id,
                            "released_allocation_id": released_allocation_id,
                            "detached_allocation_id": detached_allocation_id}), timestamp))
    except IntegrityError as exc:
        raise OperationalConflictError("Vendor already has an active demonstration slot") from exc
    return next(s for s in get_layout(database_path, zone_id)["slots"] if s["slot_id"] == slot_id)


def preview_geographic(config=None, database_path=DATABASE_PATH, obstructions=None, zone_id=PILOT_ZONE_ID):
    current = get_layout(database_path, zone_id)
    if zone_id != PILOT_ZONE_ID:
        preview = json.loads(json.dumps(current))
        preview["expected_revision"] = current["revision"]
        preview["expected_versions"] = {s["slot_id"]: s["updated_at"] for s in current["slots"]}
        return preview
    preview = gis.generate_geographic(config, obstructions=current.get("obstructions", []) if obstructions is None else obstructions)
    preview["expected_revision"] = current["revision"]
    preview["expected_versions"] = {s["slot_id"]: s["updated_at"] for s in current["slots"]}
    preview["access_points"] = current.get("access_points", {})
    preview["protected_slot_ids"] = [s["slot_id"] for s in current["slots"]
                                      if s["assigned_vendor_id"] or s["status"] == "OCCUPIED"]
    return preview


def save_geographic(proposal, *, actor, review_confirmed, database_path=DATABASE_PATH, zone_id=PILOT_ZONE_ID):
    validate_zone(zone_id)
    if proposal.get("zone_id", PILOT_ZONE_ID) != zone_id:
        raise OperationalValidationError("Layout belongs to a different pilot zone")
    if not review_confirmed:
        raise OperationalValidationError("Review the provisional preview and explicitly confirm before saving")
    boundaries = gis.boundaries_for_zone(zone_id)
    if proposal.get("source_sha256") != boundaries["source_sha256"]:
        raise OperationalConflictError("Boundary source changed. Generate a fresh preview")
    validation = gis.validate_layout(proposal, boundaries)
    if not validation["valid"]:
        raise OperationalValidationError(validation.get("reason", "Geometry review failed"))
    access_points = proposal.get("access_points", {})
    for identifier, access in access_points.items():
        if identifier not in {f["properties"]["boundary_id"] for f in boundaries["features"]}:
            raise OperationalValidationError("Unknown access-point boundary")
        gis.pose_geometry(access["longitude"], access["latitude"], 0)
        parent = next(f for f in boundaries["features"] if f["properties"]["boundary_id"] == identifier)
        if gis.metric(parent["geometry"]).distance(gis.metric(mapping(Point(access["longitude"], access["latitude"])))) > 30:
            raise OperationalValidationError("Access point must be within 30 m of its boundary")
        if not isinstance(access.get("observed"), bool) or not isinstance(access.get("note", ""), str) or len(access.get("note", "")) > 300:
            raise OperationalValidationError("Access point requires an observation flag and a short approach note")
    with transaction(database_path, immediate=True) as db:
        row = db.execute("SELECT metadata_json FROM pilot_slot_layouts WHERE zone_id = ?", (zone_id,)).fetchone()
        if not row:
            raise OperationalNotFoundError("Initialize the pilot first")
        current_metadata = json.loads(row[0])
        if proposal.get("expected_revision") != current_metadata.get("revision", "LEGACY"):
            raise OperationalConflictError("Layout changed. Reload before saving")
        current = {s["slot_id"]: s for s in db.execute(
            "SELECT * FROM pilot_slots WHERE zone_id = ? AND is_deleted = 0", (zone_id,))}
        versions = proposal.get("expected_versions", {})
        if set(versions) != set(current) or any(versions[k] != s["updated_at"] for k, s in current.items()):
            raise OperationalConflictError("Slot status or geometry changed. Reload before saving")
        proposals = {s["slot_id"]: s for s in proposal["slots"]}
        for sid, old in current.items():
            new = proposals.get(sid)
            unchanged = new and old["geometry_crs"] == "EPSG:4326" and old["parent_boundary_id"] == new["parent_boundary_id"] and gis.metric(
                json.loads(old["geometry_json"])).hausdorff_distance(gis.metric(new["geometry"])) < .00001
            if (old["assigned_vendor_id"] or old["status"] == "OCCUPIED") and not unchanged:
                raise OperationalConflictError(f"{sid} is assigned or occupied. Explicitly release its demo assignment/status before moving, deleting or regenerating it")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        for sid, old in current.items():
            if sid not in proposals:
                db.execute("UPDATE pilot_slots SET is_deleted = 1, updated_at = ? WHERE zone_id = ? AND slot_id = ?",
                           (timestamp, zone_id, sid))
                db.execute("INSERT INTO pilot_slot_events(zone_id,slot_id,actor,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                           (zone_id, sid, actor, json.dumps(dict(old)), json.dumps({"is_deleted": True}), timestamp))
        for sid, slot in proposals.items():
            pose = gis.slot_pose(slot["geometry"])
            old = current.get(sid)
            db.execute("""INSERT INTO pilot_slots(zone_id,slot_id,width_m,depth_m,x_m,y_m,geometry_json,status,
                assigned_vendor_id,validation_state,updated_at,parent_boundary_id,geometry_crs,is_deleted)
                VALUES(?,?,?,?,?,?,?, ?,?, 'ILLUSTRATIVE_UNVERIFIED',?,?,'EPSG:4326',0)
                ON CONFLICT(zone_id,slot_id) DO UPDATE SET geometry_json=excluded.geometry_json,
                x_m=excluded.x_m,y_m=excluded.y_m,width_m=excluded.width_m,depth_m=excluded.depth_m,parent_boundary_id=excluded.parent_boundary_id,
                geometry_crs='EPSG:4326',is_deleted=0,updated_at=excluded.updated_at""",
                (zone_id, sid, slot.get("width_m", 2), slot.get("depth_m", 2), *gis.TO_METRIC.transform(pose["longitude"], pose["latitude"]),
                 json.dumps(slot["geometry"]), old["status"] if old else "AVAILABLE",
                 old["assigned_vendor_id"] if old else None, timestamp, slot["parent_boundary_id"]))
            db.execute("INSERT INTO pilot_slot_events(zone_id,slot_id,actor,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                (zone_id, sid, actor, json.dumps(dict(old)) if old else "{}",
                 json.dumps({"geometry": slot["geometry"], "parent_boundary_id": slot["parent_boundary_id"]}), timestamp))
        metadata = {key: proposal.get(key) for key in ("config", "corridors", "obstructions", "rejections")}
        metadata.update({"zone_id": zone_id, "georeferenced": True, "coordinate_system": "EPSG:4326",
            "metric_crs": "EPSG:32643", "geometry_verification_status": "PROVISIONAL_NOT_SURVEYED",
            "source_sha256": boundaries["source_sha256"], "boundaries": boundaries, "access_points": access_points,
            "validation": validation, "revision": uuid.uuid4().hex,
            "width_m": proposal.get("width_m", 2), "depth_m": proposal.get("depth_m", 2), "spacing_m": proposal["config"]["spacing_m"],
            "clearance_m": proposal["config"]["clearance_m"]})
        if zone_id != PILOT_ZONE_ID:
            metadata.update({key: current_metadata.get(key) for key in ("source_provenance", "source_slot_properties", "pedestrian_clearance_assumptions", "zone_display_name", "dimension_spacing_by_boundary")})
            metadata["operational_enabled"] = True
            metadata["reviewed_by"] = actor
            metadata["reviewed_at"] = timestamp
        db.execute("UPDATE pilot_slot_layouts SET metadata_json = ? WHERE zone_id = ?", (json.dumps(metadata), zone_id))
    return get_layout(database_path, zone_id)


def preview_edit(proposal, poses=None, database_path=DATABASE_PATH, zone_id=PILOT_ZONE_ID):
    if proposal.get("zone_id", PILOT_ZONE_ID) != zone_id:
        raise OperationalValidationError("Layout belongs to a different pilot zone")
    obstruction = proposal.pop("obstruction_request", None)
    if obstruction:
        note = obstruction.get("note", "")
        if not isinstance(note, str) or len(note) > 300:
            raise OperationalValidationError("Obstruction note must be at most 300 characters")
        proposal.setdefault("obstructions", []).append({"geometry": gis.obstruction_geometry(
            obstruction["longitude"], obstruction["latitude"], obstruction.get("radius_m", .5)),
            "note": note, "provenance": "ADMIN_RECORDED_OBSERVATION"})
    for slot in proposal["slots"]:
        if slot["slot_id"] in (poses or {}):
            slot["geometry"] = gis.pose_geometry(**poses[slot["slot_id"]], width_m=slot.get("width_m", 2), depth_m=slot.get("depth_m", 2))
            slot["pose"] = gis.slot_pose(slot["geometry"])
    try:
        proposal["validation"] = gis.validate_layout(proposal)
    except OperationalValidationError as exc:
        if not obstruction:
            raise
        # An observation can invalidate the existing draft. Keep the observation
        # for explicit regeneration, but saving remains strictly prohibited.
        proposal["validation"] = {"valid": False, "reason": str(exc)}
    return proposal


def validate_zone(zone_id):
    if zone_id not in PILOT_ZONES and zone_id not in _official_zone_records(str(OFFICIAL_ZONES_PATH)):
        raise OperationalValidationError("Unknown pilot zone")


@lru_cache(maxsize=4)
def _official_zone_records(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return {row["zone_id"]: row for row in csv.DictReader(source) if row.get("zone_id")}


def _ensure_vending_zone(zone_id):
    record = _official_zone_records(str(OFFICIAL_ZONES_PATH)).get(zone_id)
    if not record or record.get("zone_type", "").upper() == "NO_VENDING":
        raise OperationalValidationError("Slots cannot be created or moved in a no-vending zone")


def initialize_drawn_zone(database_path, zone_id=INTERACTIVE_DRAW_ZONE_ID):
    """Create an empty, explicitly provisional canvas; never invent slot positions."""
    evidence = pilot_evidence(zone_id)
    metadata = {
        "zone_id": zone_id,
        "coordinate_system": "EPSG:4326",
        "metric_crs": "EPSG:32643",
        "georeferenced": True,
        "geometry_verification_status": "PROVISIONAL_NOT_SURVEYED",
        "validation_state": "ILLUSTRATIVE_UNVERIFIED",
        "operational_enabled": zone_id == INTERACTIVE_DRAW_ZONE_ID,
        "boundaries": {"type": "FeatureCollection", "features": []},
        "source_provenance": "ADMIN_DRAWN_PROVISIONAL_PLANNING_LAYOUT",
        "warning": "No independently verified vending boundary is available. Every slot requires explicit administrator confirmation and remains provisional.",
        "revision": uuid.uuid4().hex,
    }
    reference = next((f for f in evidence.get("analytical_references", []) if f.get("properties", {}).get("zone_id") == zone_id), None)
    if reference and reference.get("geometry"):
        center = shape(reference["geometry"]).centroid
        metadata["reference_point"] = {"longitude": center.x, "latitude": center.y, "use": "ANALYTICAL_REFERENCE_ONLY"}
    with transaction(database_path, immediate=True) as db:
        db.execute("INSERT INTO pilot_slot_layouts(zone_id,metadata_json,created_at) VALUES(?,?,?) ON CONFLICT DO NOTHING",
                   (zone_id, json.dumps(metadata), utc_now()))
    return get_layout(database_path, zone_id)


def _validated_drawn_rectangle(geometry, width_m=None, depth_m=None):
    try:
        polygon = shape(geometry)
    except (TypeError, ValueError, KeyError) as exc:
        raise OperationalValidationError("Slot geometry must be valid WGS84 GeoJSON") from exc
    if polygon.geom_type != "Polygon" or polygon.is_empty or not polygon.is_valid:
        raise OperationalValidationError(f"Slot must be one valid polygon: {explain_validity(polygon)}")
    if not box(73.6, 19.8, 74.0, 20.2).covers(polygon):
        raise OperationalValidationError("Slot coordinates must be WGS84 longitude/latitude within Nashik")
    projected = gis.metric(mapping(polygon))
    rectangle = projected.minimum_rotated_rectangle
    if rectangle.area <= 0 or projected.area / rectangle.area < .97:
        raise OperationalValidationError("Slot must be a square or rectangle")
    points = list(rectangle.exterior.coords)
    sides = sorted(math.dist(a, b) for a, b in zip(points, points[1:]))
    actual_width, actual_depth = sides[0], sides[-1]
    if actual_width < .5 or actual_depth > 20:
        raise OperationalValidationError("Slot sides must be between 0.5 m and 20 m")
    for requested, actual, label in ((width_m, actual_width, "width"), (depth_m, actual_depth, "length")):
        if requested is not None and abs(float(requested) - actual) > max(.35, float(requested) * .15):
            raise OperationalValidationError(f"Drawn slot {label} does not match the requested metric dimension")
    return polygon, round(actual_width, 2), round(actual_depth, 2)


def create_drawn_slot(geometry, *, actor, review_confirmed, width_m=None, depth_m=None,
                      database_path=DATABASE_PATH, zone_id=INTERACTIVE_DRAW_ZONE_ID):
    validate_zone(zone_id)
    _ensure_vending_zone(zone_id)
    if not review_confirmed:
        raise OperationalValidationError("Confirm that this is a provisional planning slot, not a verified legal boundary")
    polygon, actual_width, actual_depth = _validated_drawn_rectangle(geometry, width_m, depth_m)
    projected = gis.metric(mapping(polygon))
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with transaction(database_path, immediate=True) as db:
        layout = db.execute("SELECT metadata_json FROM pilot_slot_layouts WHERE zone_id=?" + for_update(db), (zone_id,)).fetchone()
        if not layout:
            raise OperationalNotFoundError("Initialize the slot layout before drawing")
        capacity_row = db.execute("SELECT official_capacity FROM zone_live_status WHERE zone_id=?", (zone_id,)).fetchone()
        existing = db.execute("SELECT * FROM pilot_slots WHERE zone_id=? AND is_deleted=0" + for_update(db), (zone_id,)).fetchall()
        capacity = capacity_row["official_capacity"] if capacity_row else None
        if capacity is None:
            zone_record = _official_zone_records(str(OFFICIAL_ZONES_PATH)).get(zone_id, {})
            raw_capacity = zone_record.get("capacity") or PILOT_ZONES.get(zone_id)
            capacity = int(raw_capacity) if raw_capacity is not None else None
        if capacity is None:
            raise OperationalValidationError("Official zone capacity is unavailable")
        if len(existing) >= capacity:
            raise OperationalConflictError("Created slots cannot exceed the official zone capacity")
        for row in existing:
            if row["geometry_crs"] == "EPSG:4326" and projected.intersection(gis.metric(json.loads(row["geometry_json"]))).area > .01:
                raise OperationalConflictError(f"Slot overlaps {row['slot_id']}")
        active_numbers = {
            int(row["slot_id"][1:])
            for row in existing
            if row["slot_id"].startswith("S") and row["slot_id"][1:].isdigit()
        }
        slot_number = next(
            (number for number in range(1, capacity + 1) if number not in active_numbers),
            None,
        )
        if slot_number is None:
            raise OperationalConflictError("No slot numbers remain within the official zone capacity")
        slot_id = f"S{slot_number:03d}"
        center = projected.centroid
        deleted = db.execute(
            "SELECT * FROM pilot_slots WHERE zone_id=? AND slot_id=?",
            (zone_id, slot_id),
        ).fetchone()
        if deleted:
            db.execute("""UPDATE pilot_slots SET width_m=?,depth_m=?,x_m=?,y_m=?,geometry_json=?,
                status='AVAILABLE',assigned_vendor_id=NULL,validation_state='ILLUSTRATIVE_UNVERIFIED',
                updated_at=?,parent_boundary_id=NULL,geometry_crs='EPSG:4326',is_deleted=0,
                pending_request_id=NULL,active_allocation_id=NULL,created_by=?,created_at=?
                WHERE zone_id=? AND slot_id=?""",
                (actual_width, actual_depth, center.x, center.y, json.dumps(mapping(polygon)),
                 timestamp, actor, timestamp, zone_id, slot_id))
        else:
            db.execute("""INSERT INTO pilot_slots(zone_id,slot_id,width_m,depth_m,x_m,y_m,geometry_json,status,
                assigned_vendor_id,validation_state,updated_at,parent_boundary_id,geometry_crs,is_deleted,
                pending_request_id,active_allocation_id,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,'AVAILABLE',NULL,'ILLUSTRATIVE_UNVERIFIED',?,NULL,'EPSG:4326',0,NULL,NULL,?,?)""",
                (zone_id, slot_id, actual_width, actual_depth, center.x, center.y,
                 json.dumps(mapping(polygon)), timestamp, actor, timestamp))
        db.execute("INSERT INTO pilot_slot_events(zone_id,slot_id,actor,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                   (zone_id, slot_id, actor, json.dumps(dict(deleted)) if deleted else "{}",
                    json.dumps({"action": "CREATED", "provisional": True,
                                "reused_deleted_slot_id": bool(deleted)}), timestamp))
    return next(slot for slot in get_layout(database_path, zone_id)["slots"] if slot["slot_id"] == slot_id)


def delete_drawn_slot(slot_id, *, actor, expected_updated_at, database_path=DATABASE_PATH,
                      zone_id=INTERACTIVE_DRAW_ZONE_ID):
    validate_zone(zone_id)
    _ensure_vending_zone(zone_id)
    with transaction(database_path, immediate=True) as db:
        row = db.execute("SELECT * FROM pilot_slots WHERE zone_id=? AND slot_id=?" + for_update(db), (zone_id, slot_id)).fetchone()
        if not row or row["is_deleted"]:
            raise OperationalNotFoundError("Unknown pilot slot")
        if row["updated_at"] != expected_updated_at:
            raise OperationalConflictError("Slot changed since it was loaded. Refresh before deleting.")
        if row["assigned_vendor_id"] or row["pending_request_id"] or row["active_allocation_id"] or row["status"] != "AVAILABLE":
            raise OperationalConflictError("Only an unassigned AVAILABLE slot can be deleted")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        db.execute("UPDATE pilot_slots SET is_deleted=1,updated_at=? WHERE zone_id=? AND slot_id=?", (timestamp, zone_id, slot_id))
        db.execute("INSERT INTO pilot_slot_events(zone_id,slot_id,actor,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                   (zone_id, slot_id, actor, json.dumps(dict(row)), json.dumps({"is_deleted": True}), timestamp))


def move_drawn_slot(slot_id, *, longitude, latitude, angle, width_m, depth_m, actor,
                    review_confirmed, expected_updated_at, database_path=DATABASE_PATH,
                    zone_id=INTERACTIVE_DRAW_ZONE_ID):
    validate_zone(zone_id)
    _ensure_vending_zone(zone_id)
    if not review_confirmed:
        raise OperationalValidationError("Confirm the provisional planning position before moving the slot")
    geometry = gis.pose_geometry(longitude, latitude, angle, width_m=width_m, depth_m=depth_m)
    polygon, actual_width, actual_depth = _validated_drawn_rectangle(geometry, width_m, depth_m)
    projected = gis.metric(mapping(polygon))
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with transaction(database_path, immediate=True) as db:
        current = db.execute("SELECT * FROM pilot_slots WHERE zone_id=? AND slot_id=?" + for_update(db), (zone_id, slot_id)).fetchone()
        if not current or current["is_deleted"]:
            raise OperationalNotFoundError("Unknown pilot slot")
        if current["updated_at"] != expected_updated_at:
            raise OperationalConflictError("Slot changed since it was loaded. Refresh before moving.")
        if current["assigned_vendor_id"] or current["pending_request_id"] or current["active_allocation_id"] or current["status"] != "AVAILABLE":
            raise OperationalConflictError("Only an unassigned AVAILABLE slot can be moved")
        others = db.execute("SELECT * FROM pilot_slots WHERE zone_id=? AND slot_id<>? AND is_deleted=0", (zone_id, slot_id)).fetchall()
        for row in others:
            if row["geometry_crs"] == "EPSG:4326" and projected.intersection(gis.metric(json.loads(row["geometry_json"]))).area > .01:
                raise OperationalConflictError(f"Slot overlaps {row['slot_id']}")
        center = projected.centroid
        db.execute("""UPDATE pilot_slots SET width_m=?,depth_m=?,x_m=?,y_m=?,geometry_json=?,updated_at=?
            WHERE zone_id=? AND slot_id=?""",
            (actual_width, actual_depth, center.x, center.y, json.dumps(mapping(polygon)), timestamp, zone_id, slot_id))
        db.execute("INSERT INTO pilot_slot_events(zone_id,slot_id,actor,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                   (zone_id, slot_id, actor, json.dumps(dict(current)), json.dumps({"action": "MOVED", "geometry": mapping(polygon)}), timestamp))
    return next(slot for slot in get_layout(database_path, zone_id)["slots"] if slot["slot_id"] == slot_id)


def initialize_imported(database_path, zone_id):
    layout = gis.imported_layout(zone_id)
    layout["validation"] = gis.validate_layout(layout)
    metadata = {k:v for k,v in layout.items() if k != "slots"}
    metadata["source_slot_properties"] = {s["slot_id"]: s["source_properties"] for s in layout["slots"]}
    metadata["revision"] = uuid.uuid4().hex
    with transaction(database_path, immediate=True) as db:
        exists = db.execute("SELECT 1 FROM pilot_slot_layouts WHERE zone_id=?", (zone_id,)).fetchone()
        if not exists:
            timestamp = utc_now()
            db.execute("INSERT INTO pilot_slot_layouts(zone_id,metadata_json,created_at) VALUES(?,?,?)", (zone_id,json.dumps(metadata),timestamp))
            for slot in layout["slots"]:
                pose = gis.slot_pose(slot["geometry"])
                x,y = gis.TO_METRIC.transform(pose["longitude"],pose["latitude"])
                db.execute("""INSERT INTO pilot_slots(zone_id,slot_id,width_m,depth_m,x_m,y_m,geometry_json,status,
                    assigned_vendor_id,validation_state,updated_at,parent_boundary_id,geometry_crs,is_deleted)
                    VALUES(?,?,?,?,?,?,?,'AVAILABLE',NULL,'ILLUSTRATIVE_UNVERIFIED',?,?,'EPSG:4326',0)""",
                    (zone_id,slot["slot_id"],slot["width_m"],slot["depth_m"],x,y,json.dumps(slot["geometry"]),timestamp,slot["parent_boundary_id"]))
    return get_layout(database_path,zone_id)
