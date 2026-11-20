"""
SetuHaul Logistics — FastAPI Service Boundary
Provides typed REST endpoints for Driver Chat, Feasibility Searches,
Atomic Bookings, and Operations Queue Reviews.
"""

from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.health_check import run_health_check
from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.agent.agent import SetuHaulAgent
from app.tools.schemas import (
    ConfirmAppointmentInput,
    BookingResult,
    FeasibilityResult
)

app = FastAPI(
    title="SetuHaul Logistics API",
    description="Conversational Exception Resolution & Dock Scheduling Service",
    version="1.0.0"
)

# CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
repo = DatabaseRepository()
feasibility = FeasibilityService(repo)
booking = BookingService(repo, feasibility)
agent = SetuHaulAgent()


# --- Request Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="Driver's natural language message")
    thread_id: str = Field(..., description="Unique conversation session ID")
    driver_id: Optional[str] = Field(None, description="Verified driver ID (e.g. DRV006)")
    phone: Optional[str] = Field(None, description="Driver contact phone number")


class ResolveEscalationRequest(BaseModel):
    exception_id: str = Field(..., description="ID of exception to resolve (e.g. EXC005)")
    resolution_note: str = Field(..., description="Operations supervisor resolution comment")
    action: str = Field("MANUAL_ASSIGNMENT", description="Resolution action type")


# --- Endpoints ---

@app.get("/health", tags=["System"])
def health():
    """System health check and database integrity verification."""
    res = run_health_check(repo.db_path)
    if res["status"] == "FAIL":
        raise HTTPException(status_code=500, detail=res)
    return res


@app.post("/api/chat", tags=["Driver Chat"])
def chat(request: ChatRequest):
    """
    Driver chat endpoint. Accepts natural-language messages and returns
    agent response, structured tool calls, and interaction status.
    """
    res = agent.chat(
        user_message=request.message,
        thread_id=request.thread_id,
        driver_id=request.driver_id,
        phone=request.phone
    )
    return res


@app.get("/api/shipments/{shipment_id}", tags=["Operations"])
def get_shipment(shipment_id: str):
    """Retrieve full operational and appointment context for a shipment."""
    ctx = feasibility.get_shipment_context(shipment_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found.")
    return dict(ctx)


@app.get("/api/slots/feasible", tags=["Scheduling"])
def search_slots(
    shipment_id: str = Query(..., description="Shipment ID"),
    min_time: Optional[str] = Query(None, description="Earliest slot start (ISO-8601 with +05:30)"),
    max_time: Optional[str] = Query(None, description="Latest slot start (ISO-8601)")
) -> FeasibilityResult:
    """Deterministic feasibility check returning compatible available slots."""
    return feasibility.search_feasible_slots(shipment_id, min_time=min_time, max_time=max_time)


@app.post("/api/appointments/confirm", tags=["Scheduling"])
def confirm_appointment(request: ConfirmAppointmentInput) -> BookingResult:
    """Atomic conditional booking commit protected by unique indexes."""
    return booking.confirm_appointment(request)


@app.get("/api/operations/escalations", tags=["Operations"])
def get_escalations():
    """Retrieve active human escalation tickets queued for warehouse supervisors."""
    escalations = repo.fetch_all("""
        SELECT 
            e.exception_id, e.shipment_id, e.driver_id, e.thread_id,
            e.exception_type, e.reported_at, e.severity_code,
            e.exception_status, e.description,
            d.driver_name, d.phone AS driver_phone,
            s.order_reference, s.destination_facility_id, s.priority_code
        FROM driver_exceptions e
        LEFT JOIN drivers d ON d.driver_id = e.driver_id
        LEFT JOIN shipments s ON s.shipment_id = e.shipment_id
        WHERE e.exception_status IN ('OPEN','ESCALATED','NEEDS_INFORMATION','WAITING_CONFIRMATION')
        ORDER BY e.reported_at DESC;
    """)
    return {"escalations": escalations, "count": len(escalations)}


@app.post("/api/operations/resolve", tags=["Operations"])
def resolve_escalation(request: ResolveEscalationRequest):
    """Supervisor marks an escalation as resolved with manual notes."""
    row = repo.fetch_one("SELECT exception_id FROM driver_exceptions WHERE exception_id = ?;", (request.exception_id,))
    if not row:
        raise HTTPException(status_code=404, detail=f"Exception {request.exception_id} not found.")

    repo.execute_write("""
        UPDATE driver_exceptions
        SET exception_status = 'RESOLVED',
            description = description || ' | Supervisor Note: ' || ?
        WHERE exception_id = ?;
    """, (request.resolution_note, request.exception_id))

    return {
        "status": "SUCCESS",
        "exception_id": request.exception_id,
        "resolution_note": request.resolution_note,
        "message": f"Exception {request.exception_id} successfully marked as RESOLVED."
    }
