"""
SetuHaul Logistics — Booking & State Transition Service
Manages atomic capacity commitment, revalidation, hold creation, and escalations.
Enforces SQLite BEGIN IMMEDIATE transactions and partial unique index protections.
"""

import uuid
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.tools.schemas import (
    ResultCode,
    BookingResult,
    ConfirmAppointmentInput
)


class BookingService:
    def __init__(self, repo: Optional[DatabaseRepository] = None, feasibility: Optional[FeasibilityService] = None):
        self.repo = repo or DatabaseRepository()
        self.feasibility = feasibility or FeasibilityService(self.repo)

    def record_eta_update(
        self,
        shipment_id: str,
        declared_eta_ts: str,
        source_type: str = "DRIVER_DECLARED",
        confidence_code: str = "HIGH",
        delay_reason_code: Optional[str] = None,
        note: Optional[str] = None,
        driver_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Persists a new declared arrival time and updates shipment latest ETA."""
        now_ts = datetime.now().astimezone().isoformat()
        eta_id = f"ETA-{uuid.uuid4().hex[:8].upper()}"

        with self.repo.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Insert into eta_updates
            cursor.execute("""
                INSERT INTO eta_updates (
                    eta_update_id, shipment_id, source_type, reported_by_driver_id,
                    declared_eta_ts, confidence_code, delay_reason_code, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                eta_id, shipment_id, source_type, driver_id,
                declared_eta_ts, confidence_code, delay_reason_code, note, now_ts
            ))

            # 2. Update shipment latest_eta_ts
            cursor.execute("""
                UPDATE shipments 
                SET latest_eta_ts = ?, updated_at = ?
                WHERE shipment_id = ?;
            """, (declared_eta_ts, now_ts, shipment_id))

            conn.commit()

        return {
            "result_code": ResultCode.AVAILABLE,
            "eta_update_id": eta_id,
            "shipment_id": shipment_id,
            "declared_eta_ts": declared_eta_ts,
            "confidence_code": confidence_code,
            "message": f"Recorded new ETA {declared_eta_ts} for shipment {shipment_id}."
        }

    def confirm_appointment(self, payload: ConfirmAppointmentInput) -> BookingResult:
        """
        Executes atomic revalidation and commitment inside a BEGIN IMMEDIATE transaction.
        Enforces ux_active_appointment_per_slot and ux_current_active_appointment_per_shipment.
        """
        shipment_id = payload.shipment_id
        slot_id = payload.slot_id
        now_ts = datetime.now().astimezone().isoformat()
        apt_id = f"APT-{uuid.uuid4().hex[:8].upper()}"

        try:
            with self.repo.immediate_transaction() as cursor:
                # 1. Verify shipment exists and fetch details
                cursor.execute("SELECT destination_facility_id, priority_code FROM shipments WHERE shipment_id = ?;", (shipment_id,))
                shp = cursor.fetchone()
                if not shp:
                    return BookingResult(
                        result_code=ResultCode.TOOL_FAILURE,
                        shipment_id=shipment_id,
                        status="FAILED",
                        message=f"Shipment {shipment_id} does not exist."
                    )

                # 2. Revalidate slot availability inside the lock
                cursor.execute("""
                    SELECT 
                        sl.slot_id, sl.dock_id, sl.slot_status,
                        d.dock_code, d.dock_status,
                        a.appointment_id, a.shipment_id AS occupying_shipment_id, a.appointment_status
                    FROM appointment_slots sl
                    JOIN docks d ON d.dock_id = sl.dock_id
                    LEFT JOIN appointments a ON a.slot_id = sl.slot_id 
                        AND a.appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS')
                    WHERE sl.slot_id = ?;
                """, (slot_id,))
                slot_info = cursor.fetchone()

                if not slot_info:
                    return BookingResult(
                        result_code=ResultCode.TOOL_FAILURE,
                        shipment_id=shipment_id,
                        status="FAILED",
                        message=f"Slot {slot_id} does not exist."
                    )

                # If already occupied by this exact shipment -> Idempotent replay
                if slot_info["occupying_shipment_id"] == shipment_id:
                    return BookingResult(
                        result_code=ResultCode.IDEMPOTENT_REPLAY,
                        appointment_id=slot_info["appointment_id"],
                        slot_id=slot_id,
                        shipment_id=shipment_id,
                        dock_code=slot_info["dock_code"],
                        status="CONFIRMED",
                        message=f"Idempotent replay: Slot {slot_id} is already booked for shipment {shipment_id}."
                    )

                # If occupied by another shipment, reject with SLOT_CONFLICT
                if slot_info["occupying_shipment_id"] and slot_info["occupying_shipment_id"] != shipment_id:
                    # Slot taken in race
                    alt_search = self.feasibility.search_feasible_slots(shipment_id)
                    return BookingResult(
                        result_code=ResultCode.SLOT_CONFLICT,
                        slot_id=slot_id,
                        shipment_id=shipment_id,
                        status="CONFLICT",
                        message=f"Slot {slot_id} was claimed by another shipment during selection.",
                        alternative_slots=alt_search.feasible_slots
                    )

                if slot_info["slot_status"] != "OPEN" or slot_info["dock_status"] != "ACTIVE":
                    alt_search = self.feasibility.search_feasible_slots(shipment_id)
                    return BookingResult(
                        result_code=ResultCode.STALE_OPTION,
                        slot_id=slot_id,
                        shipment_id=shipment_id,
                        status="STALE",
                        message=f"Slot {slot_id} is no longer open or active.",
                        alternative_slots=alt_search.feasible_slots
                    )

                # 3. Mark any previous active appointment for this shipment as rescheduled (is_current = 0)
                cursor.execute("""
                    UPDATE appointments 
                    SET is_current = 0, cancellation_reason = 'Rescheduled to ' || ?, updated_at = ?
                    WHERE shipment_id = ? 
                      AND is_current = 1 
                      AND appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS');
                """, (slot_id, now_ts, shipment_id))

                # 4. Insert authoritative new confirmed appointment
                # (ux_active_appointment_per_slot will raise IntegrityError if another thread slipped in)
                cursor.execute("""
                    INSERT INTO appointments (
                        appointment_id, shipment_id, slot_id, appointment_status,
                        booking_source, is_current, booked_at, confirmed_at, updated_at
                    ) VALUES (?, ?, ?, 'CONFIRMED', 'DRIVER_CHAT', 1, ?, ?, ?);
                """, (apt_id, shipment_id, slot_id, now_ts, now_ts, now_ts))

                dock_code = slot_info["dock_code"]

            return BookingResult(
                result_code=ResultCode.BOOKING_CONFIRMED,
                appointment_id=apt_id,
                slot_id=slot_id,
                shipment_id=shipment_id,
                dock_code=dock_code,
                status="CONFIRMED",
                message=f"Successfully booked slot {slot_id} (Dock {dock_code}) for shipment {shipment_id}."
            )

        except sqlite3.IntegrityError as err:
            # Caught SQLite partial unique constraint failure
            alt_search = self.feasibility.search_feasible_slots(shipment_id)
            return BookingResult(
                result_code=ResultCode.SLOT_CONFLICT,
                slot_id=slot_id,
                shipment_id=shipment_id,
                status="CONFLICT",
                message=f"Concurrency collision: {str(err)}. Slot was committed by a competing request.",
                alternative_slots=alt_search.feasible_slots
            )

    def release_appointment(self, appointment_id: str, reason: str = "Driver cancelled") -> Dict[str, Any]:
        """Releases an existing appointment or hold, freeing capacity."""
        now_ts = datetime.now().astimezone().isoformat()
        with self.repo.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE appointments
                SET appointment_status = 'CANCELLED',
                    cancelled_at = ?,
                    cancellation_reason = ?,
                    is_current = 0,
                    updated_at = ?
                WHERE appointment_id = ?;
            """, (now_ts, reason, now_ts, appointment_id))
            conn.commit()

        return {
            "result_code": ResultCode.AVAILABLE,
            "appointment_id": appointment_id,
            "status": "CANCELLED",
            "message": f"Appointment {appointment_id} released successfully."
        }

    def create_human_escalation(
        self,
        thread_id: str,
        driver_id: str,
        description: str,
        shipment_id: Optional[str] = None,
        exception_type: str = "DOCK_UNAVAILABLE",
        severity_code: str = "HIGH"
    ) -> Dict[str, Any]:
        """Records an unresolvable exception for human operations coordinator takeover."""
        now_ts = datetime.now().astimezone().isoformat()
        exc_id = f"EXC-{uuid.uuid4().hex[:8].upper()}"

        with self.repo.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Ensure thread exists in chat_threads to uphold referential integrity
            cursor.execute("SELECT thread_id FROM chat_threads WHERE thread_id = ?;", (thread_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO chat_threads (thread_id, driver_id, shipment_id, opened_at, thread_status, thread_intent)
                    VALUES (?, ?, ?, ?, 'OPEN', 'REPORT_DELAY');
                """, (thread_id, driver_id, shipment_id, now_ts))

            # 2. Insert into driver_exceptions
            cursor.execute("""
                INSERT INTO driver_exceptions (
                    exception_id, shipment_id, driver_id, thread_id, exception_type,
                    reported_at, severity_code, exception_status, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ESCALATED', ?);
            """, (
                exc_id, shipment_id, driver_id, thread_id, exception_type,
                now_ts, severity_code, description
            ))

            # 2. Update thread status to ESCALATED
            cursor.execute("""
                UPDATE chat_threads
                SET thread_status = 'ESCALATED'
                WHERE thread_id = ?;
            """, (thread_id,))

            conn.commit()

        return {
            "result_code": ResultCode.NO_FEASIBLE_SLOT,
            "escalation_id": exc_id,
            "thread_id": thread_id,
            "status": "ESCALATED",
            "message": f"Human escalation ticket {exc_id} created for operations review."
        }
