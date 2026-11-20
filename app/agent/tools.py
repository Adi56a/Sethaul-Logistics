"""
SetuHaul Logistics — LangChain Tool Implementations
Wraps deterministic FeasibilityService and BookingService into typed LangChain tools.
"""

import json
from typing import Optional, Dict, Any
from langchain_core.tools import tool
from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.tools.schemas import ConfirmAppointmentInput

# Singleton services for the agent
_repo = DatabaseRepository()
_feasibility = FeasibilityService(_repo)
_booking = BookingService(_repo, _feasibility)


def set_custom_repo(repo: DatabaseRepository):
    """Allows test fixtures to inject an isolated database repository."""
    global _repo, _feasibility, _booking
    _repo = repo
    _feasibility = FeasibilityService(_repo)
    _booking = BookingService(_repo, _feasibility)


@tool
def resolve_driver(driver_id: Optional[str] = None, phone: Optional[str] = None) -> str:
    """
    Look up driver identity and active shipments.
    Use this at the start of a conversation to find the driver's current shipment.
    Detects if the driver has multiple active shipments today requiring clarification.
    """
    res = _feasibility.resolve_driver_context(driver_id=driver_id, phone=phone)
    # Serialize cleanly for LLM
    if "selected_shipment" in res:
        res["selected_shipment"] = dict(res["selected_shipment"])
    if "active_shipments" in res:
        res["active_shipments"] = [dict(s) for s in res["active_shipments"]]
    if "driver" in res and res["driver"]:
        res["driver"] = dict(res["driver"])
    return json.dumps(res, indent=2)


@tool
def get_shipment_details(shipment_id: str) -> str:
    """
    Retrieve authoritative details for a specific shipment including product category,
    load weight (kg), required dock type (STANDARD, REEFER, HEAVY), temperature requirements,
    expected unload duration (minutes), destination facility, and current appointment.
    """
    ctx = _feasibility.get_shipment_context(shipment_id)
    if not ctx:
        return json.dumps({"error": f"Shipment {shipment_id} not found."})
    return json.dumps(dict(ctx), indent=2)


@tool
def update_driver_eta(
    shipment_id: str,
    declared_eta_ts: str,
    reason: Optional[str] = "TRAFFIC",
    confidence: Optional[str] = "HIGH",
    note: Optional[str] = None,
    driver_id: Optional[str] = None
) -> str:
    """
    Persist a driver's revised arrival estimate (ETA) into eta_updates and updates the shipment record.
    Timestamps MUST include the +05:30 offset, e.g., '2026-08-04T11:20:00+05:30'.
    """
    res = _booking.record_eta_update(
        shipment_id=shipment_id,
        declared_eta_ts=declared_eta_ts,
        source_type="DRIVER_DECLARED",
        confidence_code=confidence or "HIGH",
        delay_reason_code=reason,
        note=note,
        driver_id=driver_id
    )
    return json.dumps(res, indent=2)


@tool
def find_feasible_dock_slots(
    shipment_id: str,
    min_time: Optional[str] = None,
    max_time: Optional[str] = None
) -> str:
    """
    Deterministically search for all compatible and available dock appointment slots
    at the destination facility starting at or after min_time (or effective ETA).
    Validates dock type (standard/reefer/heavy), weight limits, unloading duration,
    operating curfew (21:00 at Jaipur), and dock breakdowns.
    """
    res = _feasibility.search_feasible_slots(shipment_id, min_time=min_time, max_time=max_time)
    data = {
        "result_code": res.result_code.value,
        "shipment_id": res.shipment_id,
        "facility_id": res.facility_id,
        "effective_eta_ts": res.effective_eta_ts,
        "message": res.message,
        "feasible_slots": [
            {
                "slot_id": s.slot_id,
                "dock_code": s.dock_code,
                "dock_type": s.dock_type,
                "slot_start_ts": s.slot_start_ts,
                "slot_end_ts": s.slot_end_ts,
                "duration_min": s.duration_min,
                "max_vehicle_weight_kg": s.max_vehicle_weight_kg
            }
            for s in res.feasible_slots
        ]
    }
    return json.dumps(data, indent=2)


@tool
def book_dock_appointment(
    shipment_id: str,
    slot_id: str,
    idempotency_key: str
) -> str:
    """
    Atomically revalidates and commits a chosen dock appointment slot for a shipment.
    Secured by database partial unique index ux_active_appointment_per_slot.
    If another truck booked the slot first, returns 'SLOT_CONFLICT' with refreshed alternative slots.
    """
    payload = ConfirmAppointmentInput(
        shipment_id=shipment_id,
        slot_id=slot_id,
        idempotency_key=idempotency_key
    )
    res = _booking.confirm_appointment(payload)
    data = {
        "result_code": res.result_code.value,
        "appointment_id": res.appointment_id,
        "slot_id": res.slot_id,
        "shipment_id": res.shipment_id,
        "dock_code": res.dock_code,
        "status": res.status,
        "message": res.message,
        "alternative_slots": [
            {
                "slot_id": s.slot_id,
                "dock_code": s.dock_code,
                "dock_type": s.dock_type,
                "slot_start_ts": s.slot_start_ts,
                "slot_end_ts": s.slot_end_ts
            }
            for s in res.alternative_slots
        ]
    }
    return json.dumps(data, indent=2)


@tool
def escalate_to_human_operator(
    thread_id: str,
    driver_id: str,
    description: str,
    shipment_id: Optional[str] = None,
    exception_type: str = "DOCK_UNAVAILABLE",
    severity: str = "HIGH"
) -> str:
    """
    Escalate an unresolvable exception to warehouse operations coordinators.
    Creates an official ticket in driver_exceptions and flags the conversation.
    Use this when NO feasible slots exist or dock breakdowns prevent automated booking.
    """
    res = _booking.create_human_escalation(
        thread_id=thread_id,
        driver_id=driver_id,
        description=description,
        shipment_id=shipment_id,
        exception_type=exception_type,
        severity_code=severity
    )
    return json.dumps(res, indent=2)


ALL_AGENT_TOOLS = [
    resolve_driver,
    get_shipment_details,
    update_driver_eta,
    find_feasible_dock_slots,
    book_dock_appointment,
    escalate_to_human_operator
]
