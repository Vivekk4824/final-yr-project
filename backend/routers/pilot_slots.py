"""Pilot Slots HTTP endpoints; existing contracts retained."""
from __future__ import annotations
from backend.core import context as dependencies
from fastapi import Request as FastAPIRequest
from fastapi import HTTPException
from backend.schemas.api import PilotGeometryEdit
from backend.schemas.api import PilotGeometryPreview
from backend.schemas.api import PilotGeometrySave
from backend.schemas.api import PilotSlotUpdate
from backend.schemas.api import PilotSlotCreate
from backend.schemas.api import PilotSlotMove
from backend.services.pilot_access import authorized_pilot_layout
from backend.services.pilot_access import pilot_operation
import backend.services.pilot_slots as pilot_slots
from backend.core.security import request_session
from fastapi import APIRouter
from fastapi import Query
from backend.repositories.database import connect
from backend.services.vendors import get_vendor_profile
router = APIRouter()

@router.get("/api/pilot/eligible-vendors")
def eligible_slot_vendors(request: FastAPIRequest, zone_id: str, q: str = "",
                          page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=50)):
    request_session(request, "ADMIN")
    pilot_slots.validate_zone(zone_id)
    db = connect(dependencies.DATABASE_PATH)
    try:
        rows = db.execute("""SELECT allocation_id,vendor_id,allocation_source FROM allocations
            WHERE zone_id=? AND status='ACTIVE' ORDER BY allocated_at DESC""", (zone_id,)).fetchall()
    finally:
        db.close()
    term = q.strip().casefold()
    candidates = []
    for row in rows:
        profile = get_vendor_profile(row["vendor_id"], database_path=dependencies.DATABASE_PATH) or {}
        candidate = {"allocation_id": row["allocation_id"], "vendor_id": row["vendor_id"],
                     "allocation_source": row["allocation_source"], "vendor_name": profile.get("full_name"),
                     "application_vendor_id": profile.get("application_vendor_id"),
                     "business_category": profile.get("business_category")}
        haystack = " ".join(str(candidate.get(key) or "") for key in ("vendor_id", "vendor_name", "application_vendor_id")).casefold()
        if not term or term in haystack:
            candidates.append(candidate)
    start = (page - 1) * page_size
    return {"vendors": candidates[start:start + page_size], "count": len(candidates),
            "page": page, "page_size": page_size}

@router.get("/api/pilot/layout")
def get_pilot_layout(request: FastAPIRequest, zone_id: str | None = None):
    return authorized_pilot_layout(request, zone_id)

@router.post("/api/pilot/initialize")
def initialize_pilot_layout(request: FastAPIRequest, zone_id: str = pilot_slots.PILOT_ZONE_ID):
    request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.initialize_demo(dependencies.DATABASE_PATH, zone_id))

@router.get("/api/pilot/slots/{slot_id}")
def get_pilot_slot(slot_id: str, request: FastAPIRequest, zone_id: str | None = None):
    layout = authorized_pilot_layout(request, zone_id)
    slot = next((s for s in layout["slots"] if s["slot_id"] == slot_id), None)
    if slot is None:
        raise HTTPException(404, "Unknown pilot slot")
    return slot

@router.patch("/api/pilot/slots/{slot_id}")
def patch_pilot_slot(slot_id: str, body: PilotSlotUpdate, request: FastAPIRequest, zone_id: str = pilot_slots.PILOT_ZONE_ID):
    session = request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.update_slot(
        slot_id, body.status, body.assigned_vendor_id, actor=session["admin_id"],
        expected_updated_at=body.expected_updated_at, database_path=dependencies.DATABASE_PATH, zone_id=zone_id))

@router.post("/api/pilot/slots", status_code=201)
def create_pilot_slot(body: PilotSlotCreate, request: FastAPIRequest, zone_id: str = pilot_slots.INTERACTIVE_DRAW_ZONE_ID):
    session = request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.create_drawn_slot(
        body.geometry, actor=session["admin_id"], review_confirmed=body.review_confirmed,
        width_m=body.width_m, depth_m=body.depth_m,
        database_path=dependencies.DATABASE_PATH, zone_id=zone_id))

@router.delete("/api/pilot/slots/{slot_id}", status_code=204)
def delete_pilot_slot(slot_id: str, expected_updated_at: str, request: FastAPIRequest,
                      zone_id: str = pilot_slots.INTERACTIVE_DRAW_ZONE_ID):
    session = request_session(request, "ADMIN")
    pilot_operation(lambda: pilot_slots.delete_drawn_slot(
        slot_id, actor=session["admin_id"], expected_updated_at=expected_updated_at,
        database_path=dependencies.DATABASE_PATH, zone_id=zone_id))
    return None

@router.patch("/api/pilot/slots/{slot_id}/geometry")
def move_pilot_slot(slot_id: str, body: PilotSlotMove, request: FastAPIRequest,
                    zone_id: str = pilot_slots.INTERACTIVE_DRAW_ZONE_ID):
    session = request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.move_drawn_slot(
        slot_id, longitude=body.longitude, latitude=body.latitude, angle=body.angle,
        width_m=body.width_m, depth_m=body.depth_m, actor=session["admin_id"],
        review_confirmed=body.review_confirmed, expected_updated_at=body.expected_updated_at,
        database_path=dependencies.DATABASE_PATH, zone_id=zone_id))

@router.post("/api/pilot/preview")
def preview_pilot_geometry(body: PilotGeometryPreview, request: FastAPIRequest, zone_id: str = pilot_slots.PILOT_ZONE_ID):
    request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.preview_geographic(body.config, dependencies.DATABASE_PATH, body.obstructions, zone_id))

@router.post("/api/pilot/validate")
def validate_pilot_edit(body: PilotGeometryEdit, request: FastAPIRequest, zone_id: str = pilot_slots.PILOT_ZONE_ID):
    request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.preview_edit(body.layout, body.poses, dependencies.DATABASE_PATH, zone_id))

@router.patch("/api/pilot/layout")
def save_pilot_geometry(body: PilotGeometrySave, request: FastAPIRequest, zone_id: str = pilot_slots.PILOT_ZONE_ID):
    session = request_session(request, "ADMIN")
    return pilot_operation(lambda: pilot_slots.save_geographic(body.layout, actor=session["admin_id"],
        review_confirmed=body.review_confirmed, database_path=dependencies.DATABASE_PATH, zone_id=zone_id))
