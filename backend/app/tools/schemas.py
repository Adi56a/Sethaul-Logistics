"""
SetuHaul Logistics — Tool Schemas & Result Contracts
Defines strict Pydantic models for inputs, outputs, and error taxonomy.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ResultCode(str, Enum):
    AVAILABLE = "AVAILABLE"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    HOLD_PENDING = "HOLD_PENDING"
    SLOT_CONFLICT = "SLOT_CONFLICT"
    STALE_OPTION = "STALE_OPTION"
    AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
    UNCERTAIN_ETA = "UNCERTAIN_ETA"
    INCOMPATIBLE_DOCK = "INCOMPATIBLE_DOCK"
    DOCK_EVENT_BLOCKED = "DOCK_EVENT_BLOCKED"
    OUTSIDE_OPERATING_HOURS = "OUTSIDE_OPERATING_HOURS"
    NO_FEASIBLE_SLOT = "NO_FEASIBLE_SLOT"
    ALREADY_CHECKED_IN = "ALREADY_CHECKED_IN"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    TOOL_FAILURE = "TOOL_FAILURE"


class DockType(str, Enum):
    STANDARD = "STANDARD"
    REEFER = "REEFER"
    HEAVY = "HEAVY"
    ANY = "ANY"


class PriorityCode(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --- Tool Input Schemas ---

class ResolveDriverInput(BaseModel):
    driver_id: Optional[str] = Field(None, description="Verified driver ID, e.g. DRV006")
    phone: Optional[str] = Field(None, description="Driver contact phone number")


class ShipmentContextInput(BaseModel):
    shipment_id: str = Field(..., description="Unique shipment identifier, e.g. SHP1006")


class SearchFeasibleSlotsInput(BaseModel):
    shipment_id: str = Field(..., description="Shipment ID to find slots for")
    min_time: Optional[str] = Field(None, description="Earliest acceptable slot start timestamp (ISO-8601)")
    max_time: Optional[str] = Field(None, description="Latest acceptable slot start timestamp (ISO-8601)")


class RecordETAUpdateInput(BaseModel):
    shipment_id: str = Field(..., description="Shipment ID")
    declared_eta_ts: str = Field(..., description="Declared arrival timestamp (ISO-8601 with +05:30)")
    source_type: str = Field("DRIVER_DECLARED", description="ORIGINAL_PLAN, DRIVER_DECLARED, OPERATIONS_OVERRIDE")
    confidence_code: str = Field("HIGH", description="LOW, MEDIUM, HIGH")
    delay_reason_code: Optional[str] = Field(None, description="TRAFFIC, BREAKDOWN, WEATHER, LOADING_DELAY, etc.")
    note: Optional[str] = Field(None, description="Context note or driver comment")


class ConfirmAppointmentInput(BaseModel):
    shipment_id: str = Field(..., description="Shipment to book")
    slot_id: str = Field(..., description="Slot ID to confirm")
    idempotency_key: str = Field(..., description="Unique client key preventing duplicate commits")


class ReleaseAppointmentInput(BaseModel):
    appointment_id: str = Field(..., description="Appointment ID to release")
    reason: str = Field(..., description="Reason for cancellation or release")


class HumanEscalationInput(BaseModel):
    thread_id: str = Field(..., description="Conversation thread ID")
    shipment_id: Optional[str] = Field(None, description="Shipment ID, if known")
    driver_id: str = Field(..., description="Driver ID")
    exception_type: str = Field(..., description="DELAY, BREAKDOWN, TRAFFIC, DOCK_UNAVAILABLE, etc.")
    severity_code: str = Field("HIGH", description="LOW, MEDIUM, HIGH, CRITICAL")
    description: str = Field(..., description="Detailed description of the unresolvable exception")
    evidence_bundle: Optional[Dict[str, Any]] = Field(None, description="Structured failure evidence")


# --- Tool Output Schemas ---

class FeasibleSlotOption(BaseModel):
    slot_id: str
    dock_id: str
    dock_code: str
    dock_type: str
    slot_start_ts: str
    slot_end_ts: str
    max_vehicle_weight_kg: int
    duration_min: int
    checks_passed: List[str]


class FeasibilityResult(BaseModel):
    result_code: ResultCode
    shipment_id: str
    facility_id: str
    effective_eta_ts: str
    feasible_slots: List[FeasibleSlotOption] = []
    message: str


class BookingResult(BaseModel):
    result_code: ResultCode
    appointment_id: Optional[str] = None
    slot_id: Optional[str] = None
    shipment_id: str
    dock_code: Optional[str] = None
    status: str
    message: str
    alternative_slots: List[FeasibleSlotOption] = []
