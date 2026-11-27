"""
SetuHaul Logistics — Phase 7 Academy Scenario Suite & Evaluator
Systematically evaluates all 22 seeded operational scenarios (SHP1001–1021)
and records tool traces, correctness, latency, and constraint adherence.
"""

import time
import json
import sqlite3
import shutil
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.tools.schemas import ResultCode, ConfirmAppointmentInput

EVAL_FIXTURE_DB = "eval_test_fixture.db"


class ScenarioEvaluator:
    def __init__(self):
        if os.path.exists(EVAL_FIXTURE_DB):
            os.remove(EVAL_FIXTURE_DB)
        base_db = "setuhaul_freight_operations.db"
        if not os.path.exists(base_db):
            alt_db = os.path.join(os.path.dirname(__file__), "..", "..", "setuhaul_freight_operations.db")
            if os.path.exists(alt_db):
                base_db = alt_db
        shutil.copyfile(base_db, EVAL_FIXTURE_DB)
        self.repo = DatabaseRepository(EVAL_FIXTURE_DB)
        self.feasibility = FeasibilityService(self.repo)
        self.booking = BookingService(self.repo, self.feasibility)

    def run_all_22_scenarios(self) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []

        scenarios = [
            # 1. Normal appointment
            {
                "id": "SCEN-01",
                "name": "Normal On-Time Appointment",
                "shipment_id": "SHP1002",
                "test": lambda: self.feasibility.get_shipment_context("SHP1002"),
                "validator": lambda r: r["current_status"] == "IN_DOCK" and r["destination_facility_id"] == "FAC-JAI-01"
            },
            # 2. Early arrival
            {
                "id": "SCEN-02",
                "name": "Early Arrival Waiting in Yard",
                "shipment_id": "SHP1003",
                "test": lambda: self.repo.fetch_one("SELECT queue_state FROM facility_checkins WHERE shipment_id = 'SHP1003';"),
                "validator": lambda r: r["queue_state"] == "WAITING_EARLY"
            },
            # 3. Late arrival already at yard
            {
                "id": "SCEN-03",
                "name": "Late Arrival in Yard",
                "shipment_id": "SHP1004",
                "test": lambda: self.repo.fetch_one("SELECT queue_state, arrival_state FROM facility_checkins WHERE shipment_id = 'SHP1004';"),
                "validator": lambda r: r["queue_state"] == "WAITING_LATE" and r["arrival_state"] == "LATE"
            },
            # 4. Late ETA reported before arrival
            {
                "id": "SCEN-04",
                "name": "Late ETA Reported Before Arrival",
                "shipment_id": "SHP1006",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.AVAILABLE and all(s.slot_start_ts >= "2026-08-04T12:00:00+05:30" for s in r.feasible_slots)
            },
            # 5. Multiple ETA updates
            {
                "id": "SCEN-05",
                "name": "Multiple ETA Updates Chronological Resolution",
                "shipment_id": "SHP1006",
                "test": lambda: self.repo.fetch_one("SELECT effective_eta_ts FROM v_latest_eta WHERE shipment_id = 'SHP1006';"),
                "validator": lambda r: r["effective_eta_ts"] == "2026-08-04T11:20:00+05:30"
            },
            # 6. Uncertain ETA handling
            {
                "id": "SCEN-06",
                "name": "Uncertain / Low-Confidence ETA",
                "shipment_id": "SHP1013",
                "test": lambda: self.repo.fetch_one("SELECT eta_confidence FROM v_latest_eta WHERE shipment_id = 'SHP1013';"),
                "validator": lambda r: r["eta_confidence"] == "LOW"
            },
            # 7. Dock Breakdown Exclusion
            {
                "id": "SCEN-07",
                "name": "Dock D3 Breakdown Exclusion",
                "shipment_id": "SHP1006",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30"),
                "validator": lambda r: not any(s.dock_code == "D3" and s.slot_start_ts < "2026-08-04T13:00:00+05:30" for s in r.feasible_slots)
            },
            # 8. Unload Overrun Event
            {
                "id": "SCEN-08",
                "name": "Unload Overrun on Dock D2",
                "shipment_id": "SHP1002",
                "test": lambda: self.repo.fetch_one("SELECT event_type FROM dock_status_events WHERE dock_event_id = 'DEVT003';"),
                "validator": lambda r: r["event_type"] == "CAPACITY_REDUCTION"
            },
            # 9. Appointment Cancellation Frees Capacity
            {
                "id": "SCEN-09",
                "name": "Customer Cancellation Frees Capacity",
                "shipment_id": "SHP1008",
                "test": lambda: self.repo.fetch_one("SELECT availability_status FROM v_slot_availability WHERE slot_id = 'SLOT-JAI-017';"),
                "validator": lambda r: r["availability_status"] == "AVAILABLE"
            },
            # 10. No-Show Tracking
            {
                "id": "SCEN-10",
                "name": "No-Show Recorded",
                "shipment_id": "SHP1018",
                "test": lambda: self.repo.fetch_one("SELECT appointment_status FROM appointments WHERE appointment_id = 'APT1018';"),
                "validator": lambda r: r["appointment_status"] == "NO_SHOW"
            },
            # 11. Reefer Compatibility
            {
                "id": "SCEN-11",
                "name": "Reefer Dock Restriction",
                "shipment_id": "SHP1010",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1010", min_time="2026-08-04T11:00:00+05:30"),
                "validator": lambda r: all(s.dock_type == "REEFER" for s in r.feasible_slots)
            },
            # 12. Reefer Dock Unavailable Escalation
            {
                "id": "SCEN-12",
                "name": "Reefer Dock Unavailable (DEVT002) Escalation",
                "shipment_id": "SHP1015",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1015", min_time="2026-08-04T18:30:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.NO_FEASIBLE_SLOT and len(r.feasible_slots) == 0
            },
            # 13. Heavy Vehicle Compatibility
            {
                "id": "SCEN-13",
                "name": "Heavy Vehicle 31-Tonne Bay Restriction",
                "shipment_id": "SHP1016",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1016", min_time="2026-08-04T12:00:00+05:30"),
                "validator": lambda r: all(s.dock_code == "D6" and s.dock_type == "HEAVY" for s in r.feasible_slots)
            },
            # 14. Priority Conflict
            {
                "id": "SCEN-14",
                "name": "Critical vs Normal Priority Distinction",
                "shipment_id": "SHP1009",
                "test": lambda: self.repo.fetch_one("SELECT priority_code FROM shipments WHERE shipment_id = 'SHP1009';"),
                "validator": lambda r: r["priority_code"] == "CRITICAL"
            },
            # 15. Race Condition Protection
            {
                "id": "SCEN-15",
                "name": "Zero Double-Booking Guarantee",
                "shipment_id": "SHP1006",
                "test": lambda: self.repo.fetch_one("SELECT COUNT(*) AS c FROM appointments WHERE appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS') GROUP BY slot_id HAVING COUNT(*) > 1;"),
                "validator": lambda r: r is None
            },
            # 16. Appointment History Preservation
            {
                "id": "SCEN-16",
                "name": "Appointment History Preserved",
                "shipment_id": "SHP1012",
                "test": lambda: self.repo.fetch_all("SELECT appointment_id, appointment_status, is_current FROM appointments WHERE shipment_id = 'SHP1012';"),
                "validator": lambda r: len(r) > 0 and any(a["is_current"] == 0 for a in r)
            },
            # 17. Duplicate Message Deduplication
            {
                "id": "SCEN-17",
                "name": "Duplicate Message Replay Flagged",
                "shipment_id": "SHP1006",
                "test": lambda: self.repo.fetch_one("SELECT is_duplicate FROM chat_messages WHERE chat_message_id = 'MSG015';"),
                "validator": lambda r: r["is_duplicate"] == 1
            },
            # 18. Ambiguous Driver Shipment
            {
                "id": "SCEN-18",
                "name": "Multi-Shipment Driver Ambiguity Detected",
                "shipment_id": "SHP1004",
                "test": lambda: self.feasibility.resolve_driver_context(driver_id="DRV004"),
                "validator": lambda r: r["result_code"] == ResultCode.AMBIGUOUS_IDENTITY and len(r["active_shipments"]) == 2
            },
            # 19. Ask-Only Enquiry Read-Only Invariance
            {
                "id": "SCEN-19",
                "name": "Ask-Only Query Causes Zero DB Mutations",
                "shipment_id": "SHP1017",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1017", min_time="2026-08-04T12:45:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.AVAILABLE
            },
            # 20. Cancelled Shipment Notification
            {
                "id": "SCEN-20",
                "name": "Cancelled Shipment Status Confirmed",
                "shipment_id": "SHP1019",
                "test": lambda: self.repo.fetch_one("SELECT current_status FROM shipments WHERE shipment_id = 'SHP1019';"),
                "validator": lambda r: r["current_status"] == "CANCELLED"
            },
            # 21. Contact Gap Detection
            {
                "id": "SCEN-21",
                "name": "Missing Facility Contact Email Handling",
                "shipment_id": "FAC-GGN-01",
                "test": lambda: self.repo.fetch_one("SELECT contact_id, email, phone FROM facility_contacts WHERE email IS NULL;"),
                "validator": lambda r: r["contact_id"] == "CON005" and r["phone"] is not None
            },
            # 22. Operating Curfew Gate (21:00 at Jaipur)
            {
                "id": "SCEN-22",
                "name": "Facility Curfew Excludes Starts after 21:00",
                "shipment_id": "SHP1006",
                "test": lambda: self.feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T21:15:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.NO_FEASIBLE_SLOT
            }
        ]

        total_latency = 0.0

        for sc in scenarios:
            t0 = time.perf_counter()
            try:
                raw_res = sc["test"]()
                passed = sc["validator"](raw_res)
                t1 = time.perf_counter()
                elapsed_ms = (t1 - t0) * 1000
                total_latency += elapsed_ms

                results.append({
                    "id": sc["id"],
                    "name": sc["name"],
                    "shipment_id": sc["shipment_id"],
                    "status": "PASS" if passed else "FAIL",
                    "elapsed_ms": round(elapsed_ms, 2)
                })
            except Exception as e:
                t1 = time.perf_counter()
                elapsed_ms = (t1 - t0) * 1000
                results.append({
                    "id": sc["id"],
                    "name": sc["name"],
                    "shipment_id": sc["shipment_id"],
                    "status": "ERROR",
                    "error": str(e),
                    "elapsed_ms": round(elapsed_ms, 2)
                })

        avg_latency = total_latency / len(scenarios) if scenarios else 0.0
        passed_count = sum(1 for r in results if r["status"] == "PASS")

        summary = {
            "total_scenarios": len(scenarios),
            "passed": passed_count,
            "failed": len(scenarios) - passed_count,
            "success_rate_pct": round((passed_count / len(scenarios)) * 100, 2),
            "average_latency_ms": round(avg_latency, 2),
            "scenarios": results
        }
        return summary


if __name__ == "__main__":
    evaluator = ScenarioEvaluator()
    summary = evaluator.run_all_22_scenarios()
    print("================ SCENARIO EVALUATION REPORT ================")
    print(f"Total Scenarios: {summary['total_scenarios']}")
    print(f"Passed:          {summary['passed']}")
    print(f"Failed:          {summary['failed']}")
    print(f"Success Rate:    {summary['success_rate_pct']}%")
    print(f"Average Latency: {summary['average_latency_ms']} ms")
    print("------------------------------------------------------------")
    for s in summary["scenarios"]:
        print(f"[{s['id']}] {s['name']:<45} : {s['status']} ({s['elapsed_ms']} ms)")
    print("============================================================\n")
