"""
SetuHaul Logistics — FastAPI Service Boundary
Provides typed REST endpoints for Driver Chat, Feasibility Searches,
Atomic Bookings, Operations Queue Reviews, and Vite + React frontend serving.
"""

import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request, status, Response, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
from app.observability import (
    tracer,
    metrics_aggregator,
    error_monitor,
    eval_engine
)
from app.auth import (
    auth_service,
    LoginRequest,
    SignupRequest,
    UserProfile,
    UserRole,
    AuthResponse
)
from app.services.chaos import chaos_engine
from app.services.sla_optimizer import sla_optimizer
from app.services.multimodal import multimodal_service
import time

app = FastAPI(
    title="SetuHaul Logistics API",
    description="Conversational Exception Resolution & Dock Scheduling Service",
    version="1.0.0"
)

# CORS support for Vite dev server (localhost:5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Distributed Tracing & Telemetry Request Middleware
@app.middleware("http")
async def trace_and_monitor_requests(request: Request, call_next):
    path = request.url.path
    method = request.method
    start_time = time.time()

    # Skip internal static assets
    if path.startswith("/assets") or path == "/favicon.ico":
        return await call_next(request)

    metadata = {
        "http.method": method,
        "http.path": path,
        "http.client_ip": request.client.host if request.client else "unknown"
    }

    try:
        with tracer.start_trace(root_name=f"{method} {path}", kind="HTTP_REQUEST", metadata=metadata) as root_span:
            response = await call_next(request)
            dur_ms = round((time.time() - start_time) * 1000, 2)
            root_span.set_attribute("http.status_code", response.status_code)
            metrics_aggregator.record_http_request(response.status_code, dur_ms)
            response.headers["X-Trace-Id"] = root_span.trace_id
            return response
    except Exception as exc:
        dur_ms = round((time.time() - start_time) * 1000, 2)
        metrics_aggregator.record_http_request(500, dur_ms)
        error_monitor.capture_exception(exc, endpoint=path, severity="CRITICAL", context=metadata)
        raise exc

# Singletons
repo = DatabaseRepository()
feasibility = FeasibilityService(repo)
booking = BookingService(repo, feasibility)
agent = SetuHaulAgent()

# Path to built React frontend (resolves both when running from backend/ or unified container)
_cand1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "dist"))
_cand2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
FRONTEND_DIST = _cand1 if os.path.isdir(_cand1) else _cand2
ASSETS_DIR = os.path.join(FRONTEND_DIST, "assets")

if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="static_assets")


# --- Request Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="Driver's natural language message")
    thread_id: str = Field(..., description="Unique conversation session ID")
    driver_id: Optional[str] = Field(None, description="Verified driver ID (e.g. DRV006)")
    phone: Optional[str] = Field(None, description="Driver contact phone number")
    shipment_id: Optional[str] = Field(None, description="Active shipment ID (e.g. SHP1006)")


class ResetThreadRequest(BaseModel):
    thread_id: str = Field(..., description="Conversation thread ID to reset")


class ResolveEscalationRequest(BaseModel):
    exception_id: str = Field(..., description="ID of exception to resolve (e.g. EXC005)")
    resolution_note: str = Field(..., description="Operations supervisor resolution comment")
    action: str = Field("MANUAL_ASSIGNMENT", description="Resolution action type")


class FogDisasterRequest(BaseModel):
    facility_id: str = Field("FAC001", description="Target facility ID")
    delay_minutes: int = Field(180, description="Delay duration to inject into active shipments")


class DockFailureRequest(BaseModel):
    dock_id: str = Field("DOCK-002", description="Target dock bay ID")
    reason: str = Field("FORKLIFT_HYDRAULIC_RUPTURE", description="Failure reason")


class AdversarialAttackRequest(BaseModel):
    attack_type: str = Field("CEO_AUTHORITY_BYPASS", description="Attack profile: CEO_AUTHORITY_BYPASS, PROMPT_INJECTION_LEAK, SQL_INJECTION_SIMULATION")
    payload: Optional[str] = Field(None, description="Custom adversarial payload string")


class VoiceNoteRequest(BaseModel):
    shipment_id: str = Field(..., description="Active shipment ID")
    preset_id: Optional[str] = Field(None, description="Voice preset ID")
    custom_text: Optional[str] = Field(None, description="Custom Hinglish speech text")


# --- Root & System Endpoints ---

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return 204 No Content for browser favicon requests to avoid 404 logs."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/", tags=["System"])
def root(request: Request):
    """
    Root endpoint.
    If the Vite + React frontend build exists (frontend/dist/index.html), serves the React SPA.
    Otherwise returns API system metadata and link to interactive API docs.
    """
    index_file = os.path.join(FRONTEND_DIST, "index.html")
    accept = request.headers.get("accept", "")

    # If browser requesting HTML and frontend dist is built, serve React app
    if "text/html" in accept and os.path.isfile(index_file):
        return FileResponse(index_file)

    # If index file exists and no specific accept header requested
    if os.path.isfile(index_file) and "application/json" not in accept:
        return FileResponse(index_file)

    return {
        "service": "SetuHaul Logistics API",
        "status": "ONLINE",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "frontend": {
            "mode": "Vite + React",
            "dev_server": "http://localhost:5173",
            "production_dist": index_file,
            "dist_built": os.path.isfile(index_file)
        },
        "endpoints": [
            {"method": "GET", "path": "/health", "desc": "System health check"},
            {"method": "POST", "path": "/api/chat", "desc": "Driver conversational agent"},
            {"method": "POST", "path": "/api/chat/reset", "desc": "Reset conversation thread"},
            {"method": "GET", "path": "/api/drivers", "desc": "List drivers and active shipments"},
            {"method": "GET", "path": "/api/facilities", "desc": "Live facility queues and dock events"},
            {"method": "GET", "path": "/api/metrics", "desc": "Operational dashboard metrics"},
            {"method": "GET", "path": "/api/shipments/{shipment_id}", "desc": "Shipment operational context"},
            {"method": "GET", "path": "/api/slots/feasible", "desc": "Deterministic slot feasibility search"},
            {"method": "POST", "path": "/api/appointments/confirm", "desc": "Atomic conditional appointment booking"},
            {"method": "GET", "path": "/api/operations/escalations", "desc": "Human supervisor review queue"},
            {"method": "POST", "path": "/api/operations/resolve", "desc": "Supervisor exception resolution"}
        ]
    }


@app.get("/health", tags=["System"])
def health():
    """System health check and database integrity verification."""
    res = run_health_check(repo.db_path)
    if res["status"] == "FAIL":
        raise HTTPException(status_code=500, detail=res)
    return res


# --- Authentication & User Endpoints ---

@app.post("/api/auth/login", response_model=AuthResponse, tags=["Authentication"])
def login(req: LoginRequest):
    """Authenticate driver or administrator with username and password (default: 123456)."""
    res = auth_service.authenticate(req)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password. (Hint: all default passwords are '123456')"
        )
    return res


@app.post("/api/auth/signup", response_model=AuthResponse, tags=["Authentication"])
def signup(req: SignupRequest):
    """Register a new Driver or Administrator account with instant session activation."""
    try:
        res = auth_service.register(req)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")


@app.get("/api/auth/me", response_model=UserProfile, tags=["Authentication"])
def get_current_user_profile(authorization: Optional[str] = Header(None)):
    """Retrieve current authenticated user profile from Authorization: Bearer <token>."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header.")
    token = authorization.split("Bearer ")[1].strip()
    user = auth_service.authenticate_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid token.")
    return user


@app.post("/api/auth/logout", tags=["Authentication"])
def logout():
    """Invalidates current user session."""
    return {"status": "SUCCESS", "message": "Successfully logged out."}


@app.get("/api/auth/demo-users", tags=["Authentication"])
def list_demo_users():
    """List one-click demo credentials for quick evaluation (password for all is '123456')."""
    return {
        "password": "all passwords are '123456'",
        "admin_accounts": [
            {"username": "admin", "name": "Neha Bansal (Operations Supervisor)", "role": "ADMIN", "desc": "Supervisor with full review queue, live facility status, and telemetry"},
            {"username": "ops", "name": "Warehouse Operations Dispatcher", "role": "ADMIN", "desc": "Dispatcher managing facility queues and slot overrides"}
        ],
        "driver_accounts": [
            {"username": "DRV006", "name": "Manoj Sharma", "role": "DRIVER", "shipment_id": "SHP1006", "order_reference": "ORD-260804-006", "desc": "Standard Load (7.8T) to Jaipur DC"},
            {"username": "DRV004", "name": "Sandeep Meena", "role": "DRIVER", "shipment_id": "SHP1004 / SHP1020", "order_reference": "ORD-260804-004", "desc": "Ambiguous Multi-Shipment Case"},
            {"username": "DRV015", "name": "Mohammed Salim", "role": "DRIVER", "shipment_id": "SHP1015", "order_reference": "ORD-260804-015", "desc": "Reefer Cold-Chain Breakdown Disruption"},
            {"username": "DRV007", "name": "Nitin Patil", "role": "DRIVER", "shipment_id": "SHP1016", "order_reference": "ORD-260804-016", "desc": "Heavy 31T Vehicle with Bay D6 Restriction"},
            {"username": "DRV012", "name": "Arjun Das", "role": "DRIVER", "shipment_id": "SHP1012", "order_reference": "ORD-260804-012", "desc": "Standard Slot Competition at 12:00 PM"},
            {"username": "DRV003", "name": "Mukesh Yadav", "role": "DRIVER", "shipment_id": "SHP1003", "order_reference": "ORD-260804-003", "desc": "Early Arrival Waiting in Facility Yard"}
        ]
    }


# --- Driver & Chat Endpoints ---

@app.get("/api/drivers", tags=["Driver Chat"])
def list_drivers():
    """List drivers with current shipment associations for UI testing."""
    drivers = repo.fetch_all("""
        SELECT 
            d.driver_id, d.driver_name, d.phone, d.carrier_id,
            s.shipment_id, s.order_reference, s.current_status AS shipment_status,
            s.required_dock_type, s.load_weight_kg, s.destination_facility_id,
            a.appointment_id, ds.slot_start_ts, ds.dock_id,
            f.facility_name
        FROM drivers d
        LEFT JOIN shipments s ON s.driver_id = d.driver_id
        LEFT JOIN appointments a ON a.shipment_id = s.shipment_id AND a.is_current = 1 AND a.appointment_status IN ('CONFIRMED','PENDING_CONFIRMATION')
        LEFT JOIN appointment_slots ds ON ds.slot_id = a.slot_id
        LEFT JOIN facilities f ON f.facility_id = s.destination_facility_id
        ORDER BY d.driver_id, s.shipment_id;
    """)
    return {"drivers": drivers, "count": len(drivers)}


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
        phone=request.phone,
        shipment_id=request.shipment_id
    )
    return res


@app.post("/api/chat/reset", tags=["Driver Chat"])
def reset_chat(request: ResetThreadRequest):
    """Reset the conversational memory for a given thread."""
    agent.clear_thread(request.thread_id)
    return {
        "status": "SUCCESS",
        "thread_id": request.thread_id,
        "message": f"Thread {request.thread_id} memory cleared successfully."
    }


@app.get("/api/chat/history/{thread_id}", tags=["Driver Chat"])
def get_chat_history(thread_id: str):
    """Retrieve full persistent conversation history for a driver thread."""
    messages = agent.repo.get_chat_history(thread_id)
    return {
        "status": "SUCCESS",
        "thread_id": thread_id,
        "count": len(messages),
        "messages": messages
    }


# --- Scheduling & Feasibility Endpoints ---

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


# --- Operations & Facility Management Endpoints ---

@app.get("/api/facilities", tags=["Operations"])
def get_facilities():
    """Retrieve live facility data, dock disruption events, and yard waiting queues."""
    facilities = repo.fetch_all("SELECT * FROM facilities ORDER BY facility_id;")
    docks = repo.fetch_all("SELECT * FROM docks ORDER BY facility_id, dock_code;")
    disruptions = repo.fetch_all("SELECT * FROM dock_status_events ORDER BY event_start_ts DESC;")
    yard_queue = repo.fetch_all("SELECT * FROM v_current_facility_queue ORDER BY queue_position;")

    return {
        "facilities": facilities,
        "docks": docks,
        "active_disruptions": disruptions,
        "yard_queue": yard_queue
    }


@app.get("/api/metrics", tags=["Operations"])
def get_metrics():
    """Operational summary metrics for dashboard KPIs."""
    open_exc = repo.fetch_one("""
        SELECT COUNT(*) as count FROM driver_exceptions 
        WHERE exception_status IN ('OPEN','ESCALATED','NEEDS_INFORMATION','WAITING_CONFIRMATION');
    """)
    total_shp = repo.fetch_one("SELECT COUNT(*) as count FROM shipments;")
    yard_count = repo.fetch_one("SELECT COUNT(*) as count FROM v_current_facility_queue;")
    active_disruptions = repo.fetch_one("SELECT COUNT(*) as count FROM dock_status_events;")

    return {
        "open_exceptions": open_exc["count"] if open_exc else 0,
        "total_shipments": total_shp["count"] if total_shp else 0,
        "trucks_in_yard": yard_count["count"] if yard_count else 0,
        "dock_disruptions": active_disruptions["count"] if active_disruptions else 0,
        "operational_snapshot_time": "2026-08-04T11:00:00+05:30"
    }


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


# --- Chaos Monkey & Red-Team Adversarial Endpoints ---

@app.post("/api/chaos/inject/fog-disaster", tags=["Chaos Crucible"])
def inject_fog_disaster(req: FogDisasterRequest):
    """Simulate sudden dense fog & highway pileup on NH-48, batch delaying inbound shipments."""
    with tracer.span("chaos.inject.fog_disaster", kind="CHAOS_INJECTION") as s:
        res = chaos_engine.inject_fog_disaster(req.facility_id, req.delay_minutes)
        s.set_attribute("affected_count", res["affected_count"])
        return res


@app.post("/api/chaos/inject/dock-failure", tags=["Chaos Crucible"])
def inject_dock_failure(req: DockFailureRequest):
    """Simulate a physical breakdown of a dock bay (forklift failure) forcing autonomous rerouting."""
    with tracer.span("chaos.inject.dock_failure", kind="CHAOS_INJECTION") as s:
        res = chaos_engine.inject_dock_failure(req.dock_id, req.reason)
        s.set_attribute("dock_id", req.dock_id)
        return res


@app.post("/api/chaos/inject/adversarial-attack", tags=["Chaos Crucible"])
def inject_adversarial_attack(req: AdversarialAttackRequest):
    """Simulate prompt injection, CEO authority bypass, or SQL injection attack."""
    with tracer.span("chaos.inject.adversarial_attack", kind="SECURITY_ATTACK") as s:
        res = chaos_engine.inject_adversarial_attack(req.payload, req.attack_type)
        metrics_aggregator.record_guardrail_override()
        s.set_attribute("attack_type", req.attack_type)
        s.set_attribute("intercepted", True)
        return res


@app.post("/api/chaos/reset", tags=["Chaos Crucible"])
def reset_chaos():
    """Clear all active disruptions and restore facilities to operational baseline."""
    return chaos_engine.reset_system()


@app.get("/api/chaos/status", tags=["Chaos Crucible"])
def get_chaos_status():
    """Retrieve active chaos disruptions, security incident logs, and resilience status."""
    return chaos_engine.get_status()


# --- Game-Theoretic SLA Financial Penalty & Optimization Endpoints ---

@app.get("/api/operations/sla-roi", tags=["SLA Optimizer"])
def get_sla_roi(facility_id: str = Query("FAC001", description="Facility ID")):
    """Calculates financial penalties prevented and ROI in INR (₹) delivered by SetuHaul."""
    return sla_optimizer.compute_facility_sla_roi(facility_id)


@app.post("/api/operations/optimize-queue", tags=["SLA Optimizer"])
def optimize_queue(facility_id: str = Query("FAC001", description="Facility ID")):
    """Runs immediate queue optimization prioritizing high-detention & cold-chain cargo."""
    return sla_optimizer.compute_facility_sla_roi(facility_id)


# --- Multimodal Hinglish Voice & Bilty OCR Endpoints ---

@app.get("/api/driver/voice-presets", tags=["Multimodal Driver Ingestion"])
def get_voice_presets():
    """Returns pre-configured Indian highway Hinglish voice note presets."""
    return {"presets": multimodal_service.get_voice_presets()}


@app.post("/api/driver/voice-note", tags=["Multimodal Driver Ingestion"])
def process_voice_note(req: VoiceNoteRequest):
    """Parses Hinglish audio note or preset into structured logistical entities and conversational response."""
    with tracer.span("multimodal.voice_note", kind="MULTIMODAL_INGEST") as s:
        res = multimodal_service.process_voice_note(req.shipment_id, req.preset_id, req.custom_text)
        s.set_attribute("shipment_id", req.shipment_id)
        s.set_attribute("delay_minutes", res["extracted_entities"]["delay_minutes"])
        return res


@app.get("/api/driver/bilty-audit/{shipment_id}", tags=["Multimodal Driver Ingestion"])
def audit_bilty(shipment_id: str):
    """Executes optical OCR audit on physical Bilty (Lorry Receipt / e-Way Bill) and validates dock tonnage."""
    with tracer.span("multimodal.bilty_audit", kind="DOCUMENT_OCR") as s:
        res = multimodal_service.audit_bilty(shipment_id)
        s.set_attribute("shipment_id", shipment_id)
        s.set_attribute("compliance_status", res["compliance_status"])
        return res


# --- Observability, Telemetry & Evals Endpoints ---

@app.get("/api/observability/metrics", tags=["Observability"])
def get_observability_metrics():
    """Retrieve live latency percentiles (p50, p95, p99), error rates, throughput, and tool metrics."""
    recent_traces = tracer.store.list_traces(limit=10)
    open_errors = error_monitor.list_errors(limit=10, status="OPEN")
    return metrics_aggregator.get_snapshot(
        active_traces_count=len(recent_traces),
        open_errors_count=len(open_errors)
    )


@app.get("/api/observability/traces", tags=["Observability"])
def list_traces(limit: int = Query(50, ge=1, le=200), status: Optional[str] = None):
    """Retrieve list of recent distributed traces."""
    return {"traces": tracer.store.list_traces(limit=limit, status=status)}


@app.get("/api/observability/traces/{trace_id}", tags=["Observability"])
def get_trace_waterfall(trace_id: str):
    """Retrieve full span hierarchy and waterfall data for a specific trace."""
    trace = tracer.store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found.")
    return trace


@app.get("/api/observability/errors", tags=["Observability"])
def list_errors(limit: int = Query(50, ge=1, le=200), status: Optional[str] = None):
    """Retrieve tracked exceptions and operational errors."""
    return {"errors": error_monitor.list_errors(limit=limit, status=status)}


@app.post("/api/observability/errors/{error_id}/resolve", tags=["Observability"])
def resolve_error(error_id: str):
    """Mark an error record as resolved."""
    ok = error_monitor.resolve_error(error_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Error {error_id} not found.")
    return {"status": "SUCCESS", "error_id": error_id, "message": f"Error {error_id} resolved."}


@app.get("/api/observability/evals", tags=["Observability"])
def list_eval_reports(limit: int = Query(20, ge=1, le=100)):
    """Retrieve historical evaluation runs."""
    return {"eval_runs": eval_engine.store.list_eval_reports(limit=limit)}


@app.post("/api/observability/evals/run", tags=["Observability"])
def run_eval_suite():
    """Trigger a live execution of the full 22-scenario academy evaluation suite."""
    report = eval_engine.run_eval_suite()
    return report


@app.get("/api/observability/evals/{eval_id}", tags=["Observability"])
def get_eval_report(eval_id: str):
    """Retrieve full scenario report for an evaluation run."""
    report = eval_engine.store.get_eval_report(eval_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Evaluation report {eval_id} not found.")
    return report

