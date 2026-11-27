"""
SetuHaul Logistics — Deterministic Feasibility Engine
Evaluates slot compatibility, operating rules, dock events, and unloading durations.
Does NOT rely on an LLM for any physical or operational check.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from app.repositories.db import DatabaseRepository
from app.tools.schemas import (
    ResultCode,
    FeasibleSlotOption,
    FeasibilityResult
)


class FeasibilityService:
    def __init__(self, repo: Optional[DatabaseRepository] = None):
        self.repo = repo or DatabaseRepository()

    def resolve_driver_context(self, driver_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves driver identity and checks for active shipments.
        Detects multi-shipment ambiguity safely (e.g. DRV004).
        """
        if not driver_id and not phone:
            return {
                "result_code": ResultCode.AMBIGUOUS_IDENTITY,
                "message": "Neither driver_id nor phone was provided."
            }

        # 1. Look up driver
        if driver_id:
            driver = self.repo.fetch_one("SELECT * FROM drivers WHERE driver_id = ?;", (driver_id,))
        else:
            driver = self.repo.fetch_one("SELECT * FROM drivers WHERE phone = ?;", (phone,))

        if not driver:
            return {
                "result_code": ResultCode.AMBIGUOUS_IDENTITY,
                "message": f"Driver not found with identifier: {driver_id or phone}"
            }

        drv_id = driver["driver_id"]

        # 2. Query active shipments assigned to driver
        shipments = self.repo.fetch_all("""
            SELECT shipment_id, order_reference, current_status, origin_city, 
                   destination_facility_id, planned_departure_ts, original_eta_ts
            FROM shipments
            WHERE driver_id = ? 
              AND current_status IN ('PLANNED','ASSIGNED','IN_TRANSIT','WAITING')
            ORDER BY planned_departure_ts;
        """, (drv_id,))

        if len(shipments) == 0:
            return {
                "result_code": ResultCode.TOOL_FAILURE,
                "driver": driver,
                "active_shipments": [],
                "message": f"No active in-transit shipments found for driver {driver['driver_name']}."
            }
        elif len(shipments) == 1:
            return {
                "result_code": ResultCode.AVAILABLE,
                "driver": driver,
                "selected_shipment": shipments[0],
                "active_shipments": shipments,
                "is_ambiguous": False,
                "message": f"Identified active shipment {shipments[0]['shipment_id']} for driver {driver['driver_name']}."
            }
        else:
            # Multi-shipment ambiguity detected (e.g. DRV004 with SHP1004 & SHP1020)
            return {
                "result_code": ResultCode.AMBIGUOUS_IDENTITY,
                "driver": driver,
                "active_shipments": shipments,
                "is_ambiguous": True,
                "message": (
                    f"Driver {driver['driver_name']} has {len(shipments)} active shipments today "
                    f"({', '.join([s['order_reference'] for s in shipments])}). "
                    "Clarification required to determine which shipment is delayed."
                )
            }

    def get_shipment_context(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves comprehensive authoritative context for a single shipment."""
        return self.repo.fetch_one("""
            SELECT 
                s.*,
                d.driver_name, d.phone AS driver_phone,
                v.registration_number, v.vehicle_type_code,
                f.facility_name, f.timezone, f.open_time, f.close_time,
                le.effective_eta_ts, le.eta_source, le.eta_confidence,
                ap.appointment_id AS current_appointment_id,
                ap.slot_id AS current_slot_id,
                ap.appointment_status AS current_appointment_status
            FROM shipments s
            JOIN drivers d ON d.driver_id = s.driver_id
            JOIN vehicles v ON v.vehicle_id = s.vehicle_id
            JOIN facilities f ON f.facility_id = s.destination_facility_id
            JOIN v_latest_eta le ON le.shipment_id = s.shipment_id
            LEFT JOIN appointments ap ON ap.shipment_id = s.shipment_id 
                AND ap.is_current = 1 
                AND ap.appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS')
            WHERE s.shipment_id = ?;
        """, (shipment_id,))

    def search_feasible_slots(
        self,
        shipment_id: str,
        min_time: Optional[str] = None,
        max_time: Optional[str] = None
    ) -> FeasibilityResult:
        """
        Pure deterministic feasibility engine.
        Evaluates candidate slots against dock type, weight, operating hours,
        unload duration, active bookings, and dock status events.
        """
        ctx = self.get_shipment_context(shipment_id)
        if not ctx:
            return FeasibilityResult(
                result_code=ResultCode.TOOL_FAILURE,
                shipment_id=shipment_id,
                facility_id="UNKNOWN",
                effective_eta_ts="UNKNOWN",
                message=f"Shipment {shipment_id} not found."
            )

        facility_id = ctx["destination_facility_id"]
        effective_eta = min_time or ctx["effective_eta_ts"]
        load_weight = ctx["load_weight_kg"]
        req_dock_type = ctx["required_dock_type"]
        temp_required = bool(ctx["temperature_control_required"])
        unload_min = ctx["expected_unload_min"]

        # 1. Fetch Facility Rules
        rules = self.repo.fetch_all("""
            SELECT rule_type, rule_value 
            FROM facility_rules 
            WHERE facility_id = ? AND active_flag = 1;
        """, (facility_id,))
        rule_dict = {r["rule_type"]: r["rule_value"] for r in rules}

        last_start_time = rule_dict.get("LAST_NEW_START_TIME", "21:00")
        heavy_weight_threshold = int(rule_dict.get("HEAVY_DOCK_REQUIRED_KG", 25000))

        # Check weight vs heavy dock requirement
        is_heavy = load_weight > heavy_weight_threshold

        # 2. Query candidate slots at facility starting at or after effective ETA
        slots_query = """
            SELECT 
                sl.slot_id, sl.facility_id, sl.dock_id, sl.slot_start_ts, sl.slot_end_ts, sl.slot_status,
                d.dock_code, d.dock_type, d.supports_refrigerated, d.max_vehicle_weight_kg, d.dock_status,
                a.appointment_id, a.appointment_status
            FROM appointment_slots sl
            JOIN docks d ON d.dock_id = sl.dock_id
            LEFT JOIN appointments a ON a.slot_id = sl.slot_id 
                AND a.appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS')
            WHERE sl.facility_id = ?
              AND sl.slot_start_ts >= ?
        """
        params: List[Any] = [facility_id, effective_eta]

        if max_time:
            slots_query += " AND sl.slot_start_ts <= ?"
            params.append(max_time)

        slots_query += " ORDER BY sl.slot_start_ts, d.dock_code;"

        candidates = self.repo.fetch_all(slots_query, tuple(params))

        # 3. Query active dock events (breakdowns, maintenance)
        dock_events = self.repo.fetch_all("""
            SELECT dock_id, event_type, event_start_ts, event_end_ts, reason 
            FROM dock_status_events;
        """)

        feasible_slots: List[FeasibleSlotOption] = []
        rejection_reasons: Dict[str, int] = {}

        for slot in candidates:
            slot_id = slot["slot_id"]
            checks_passed = []

            # Check A: Slot status OPEN
            if slot["slot_status"] != "OPEN":
                rejection_reasons["SLOT_NOT_OPEN"] = rejection_reasons.get("SLOT_NOT_OPEN", 0) + 1
                continue
            checks_passed.append("SLOT_OPEN")

            # Check B: No active booking
            if slot["appointment_id"] is not None:
                rejection_reasons["SLOT_OCCUPIED"] = rejection_reasons.get("SLOT_OCCUPIED", 0) + 1
                continue
            checks_passed.append("NO_ACTIVE_BOOKING")

            # Check C: Dock operational status ACTIVE
            if slot["dock_status"] != "ACTIVE":
                rejection_reasons["DOCK_INACTIVE"] = rejection_reasons.get("DOCK_INACTIVE", 0) + 1
                continue
            checks_passed.append("DOCK_ACTIVE")

            # Check D: Dock Status Events (Breakdown / Maintenance overlapping slot)
            event_blocked = False
            for evt in dock_events:
                if evt["dock_id"] == slot["dock_id"]:
                    evt_start = evt["event_start_ts"]
                    evt_end = evt["event_end_ts"] or "9999-12-31"
                    # Overlap if slot_start < evt_end and slot_end > evt_start
                    if slot["slot_start_ts"] < evt_end and slot["slot_end_ts"] > evt_start:
                        event_blocked = True
                        break
            if event_blocked:
                rejection_reasons["DOCK_EVENT_BLOCKED"] = rejection_reasons.get("DOCK_EVENT_BLOCKED", 0) + 1
                continue
            checks_passed.append("NO_DOCK_BREAKDOWN")

            # Check E: Reefer / Temperature compatibility
            if temp_required or req_dock_type == "REEFER":
                if not slot["supports_refrigerated"] or slot["dock_type"] != "REEFER":
                    rejection_reasons["REEFER_INCOMPATIBLE"] = rejection_reasons.get("REEFER_INCOMPATIBLE", 0) + 1
                    continue
            else:
                # Standard / non-reefer loads must not consume scarce reefer bays
                if slot["dock_type"] == "REEFER":
                    rejection_reasons["RESERVED_FOR_REEFER"] = rejection_reasons.get("RESERVED_FOR_REEFER", 0) + 1
                    continue
            checks_passed.append("TEMPERATURE_COMPATIBLE")

            # Check F: Heavy dock compatibility
            if is_heavy or req_dock_type == "HEAVY":
                if slot["dock_type"] != "HEAVY":
                    rejection_reasons["HEAVY_DOCK_REQUIRED"] = rejection_reasons.get("HEAVY_DOCK_REQUIRED", 0) + 1
                    continue
            else:
                # Non-heavy loads avoid occupying scarce heavy bay
                if slot["dock_type"] == "HEAVY":
                    rejection_reasons["RESERVED_FOR_HEAVY"] = rejection_reasons.get("RESERVED_FOR_HEAVY", 0) + 1
                    continue
            checks_passed.append("WEIGHT_CLASS_COMPATIBLE")

            # Check G: Weight capacity limit
            if load_weight > slot["max_vehicle_weight_kg"]:
                rejection_reasons["WEIGHT_EXCEEDED"] = rejection_reasons.get("WEIGHT_EXCEEDED", 0) + 1
                continue
            checks_passed.append("MAX_WEIGHT_SATISFIED")

            # Check H: Slot duration vs unload duration
            # Slot duration calculation
            try:
                # ISO-8601 strings, e.g., '2026-08-04T10:00:00+05:30'
                start_dt = datetime.fromisoformat(slot["slot_start_ts"])
                end_dt = datetime.fromisoformat(slot["slot_end_ts"])
                slot_duration_min = int((end_dt - start_dt).total_seconds() / 60)
            except Exception:
                slot_duration_min = 60

            if slot_duration_min < unload_min:
                rejection_reasons["DURATION_INSUFFICIENT"] = rejection_reasons.get("DURATION_INSUFFICIENT", 0) + 1
                continue
            checks_passed.append("DURATION_SUFFICIENT")

            # Check I: Last new start time curfew (21:00 at Jaipur)
            slot_time_str = slot["slot_start_ts"].split("T")[1][:5]
            if slot_time_str > last_start_time:
                rejection_reasons["PAST_CURFEW"] = rejection_reasons.get("PAST_CURFEW", 0) + 1
                continue
            checks_passed.append("WITHIN_OPERATING_HOURS")

            feasible_slots.append(FeasibleSlotOption(
                slot_id=slot["slot_id"],
                dock_id=slot["dock_id"],
                dock_code=slot["dock_code"],
                dock_type=slot["dock_type"],
                slot_start_ts=slot["slot_start_ts"],
                slot_end_ts=slot["slot_end_ts"],
                max_vehicle_weight_kg=slot["max_vehicle_weight_kg"],
                duration_min=slot_duration_min,
                checks_passed=checks_passed
            ))

        if not feasible_slots:
            return FeasibilityResult(
                result_code=ResultCode.NO_FEASIBLE_SLOT,
                shipment_id=shipment_id,
                facility_id=facility_id,
                effective_eta_ts=effective_eta,
                feasible_slots=[],
                message=(
                    f"No feasible compatible slots found for {shipment_id} after {effective_eta}. "
                    f"Rejections: {dict(rejection_reasons)}. Human operations review required."
                )
            )

        return FeasibilityResult(
            result_code=ResultCode.AVAILABLE,
            shipment_id=shipment_id,
            facility_id=facility_id,
            effective_eta_ts=effective_eta,
            feasible_slots=feasible_slots,
            message=f"Found {len(feasible_slots)} feasible dock slots compatible with {shipment_id}."
        )
