"""Extracted services pilot_access helpers; behavior retained."""
from __future__ import annotations
from backend.core import context as dependencies
from fastapi import Request as FastAPIRequest
from fastapi import HTTPException
from backend.repositories.database import OperationalConflictError
from backend.repositories.database import OperationalNotFoundError
from backend.repositories.database import OperationalValidationError
import backend.services.pilot_slots as pilot_slots
from backend.core.security import request_session

def pilot_operation(operation):
    try:
        return operation()
    except OperationalNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except OperationalConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OperationalValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, "Invalid pilot geometry or navigation payload") from exc

def authorized_pilot_layout(request: FastAPIRequest, zone_id: str | None = None):
    session = request_session(request, "ADMIN", "VENDOR")
    if session["role"] == "VENDOR":
        with pilot_slots.transaction(dependencies.DATABASE_PATH) as db:
            allocation = db.execute("""SELECT a.zone_id FROM allocations a
                WHERE a.vendor_id = ? AND a.status = 'ACTIVE'""",
                (session["vendor_id"],)).fetchone()
        if zone_id is None:
            if not allocation or allocation["zone_id"] not in pilot_slots.PILOT_ZONES:
                raise HTTPException(403, "A current allocation to a slot-enabled zone is required when no zone is selected")
            zone_id = allocation["zone_id"]
        if zone_id not in pilot_slots.PILOT_ZONES:
            raise HTTPException(404, "Slot mapping is not enabled for this zone")
    zone_id = zone_id or pilot_slots.PILOT_ZONE_ID
    layout = pilot_operation(lambda: pilot_slots.get_layout(dependencies.DATABASE_PATH, zone_id))
    if session["role"] == "VENDOR":
        layout["my_slot_id"] = next((s["slot_id"] for s in layout["slots"]
                                      if s["assigned_vendor_id"] == session["vendor_id"]), None)
        # No admin audit/source bookkeeping or other vendors' private identities.
        layout.pop("source_slot_properties", None)
        layout.pop("reviewed_by", None)
        for slot in layout["slots"]:
            if slot["assigned_vendor_id"] != session["vendor_id"]:
                slot["assigned_vendor_id"] = None
            slot.pop("pending_request_id", None)
            slot.pop("active_allocation_id", None)
            slot.pop("created_by", None)
    return layout
