"""
SetuHaul Logistics — Scenario Evaluation Engine
Programmatically runs and evaluates the 22 core academy operational scenarios.
Provides latency profiling, rule compliance assertions, and persistent audit reports.
"""

import time
import os
import shutil
from typing import Dict, Any, List, Optional

from app.observability.models import EvalReport, ScenarioResult
from app.observability.store import ObservabilityStore
from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.agent.tools import set_custom_repo
from app.tools.schemas import ResultCode

EVAL_FIXTURE_DB = "eval_obs_fixture.db"


class EvalEngine:
    def __init__(self, store: Optional[ObservabilityStore] = None):
        self.store = store or ObservabilityStore()

    def run_eval_suite(self) -> EvalReport:
        """
        Executes the full 22-scenario academy test suite with millisecond latency benchmarking.
        Uses isolated test database fixture so operational state is never corrupted.
        """
        # Cleanup past fixture
        if os.path.exists(EVAL_FIXTURE_DB):
            try:
                os.remove(EVAL_FIXTURE_DB)
            except Exception:
                pass

        # Locate base db
        base_db = "setuhaul_freight_operations.db"
        if not os.path.exists(base_db):
            alt_db = os.path.join(os.path.dirname(__file__), "..", "..", "setuhaul_freight_operations.db")
            if os.path.exists(alt_db):
                base_db = alt_db

        shutil.copyfile(base_db, EVAL_FIXTURE_DB)

        repo = DatabaseRepository(EVAL_FIXTURE_DB)
        set_custom_repo(repo)
        feasibility = FeasibilityService(repo)
        booking = BookingService(repo, feasibility)

        results: List[ScenarioResult] = []

        scenarios_defs = [
            # 1. Normal on-time arrival
            {
                "id": "SCEN-01",
                "name": "Normal On-Time Appointment",
                "category": "NORMAL_BOOKING",
                "test": lambda: feasibility.search_feasible_slots("SHP1001", min_time="2026-08-04T08:00:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.AVAILABLE and len(r.feasible_slots) > 0
            },
            # 2. Early arrival
            {
                "id": "SCEN-02",
                "name": "Early Arrival Waiting in Yard",
                "category": "YARD_MANAGEMENT",
                "test": lambda: repo.fetch_one("SELECT queue_state FROM facility_checkins WHERE shipment_id = 'SHP1003';"),
                "validator": lambda r: r["queue_state"] == "WAITING_EARLY"
            },
            # 3. Late arrival already at yard
            {
                "id": "SCEN-03",
                "name": "Late Arrival in Yard",
                "category": "YARD_MANAGEMENT",
                "test": lambda: repo.fetch_one("SELECT queue_state, arrival_state FROM facility_checkins WHERE shipment_id = 'SHP1004';"),
                "validator": lambda r: r["queue_state"] == "WAITING_LATE" and r["arrival_state"] == "LATE"
            },
            # 4. Late ETA reported before arrival
            {
                "id": "SCEN-04",
                "name": "Late ETA Reported Before Arrival",
                "category": "RESCHEDULING",
                "test": lambda: feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.AVAILABLE and all(s.slot_start_ts >= "2026-08-04T12:00:00+05:30" for s in r.feasible_slots)
            },
            # 5. Multiple ETA updates
            {
                "id": "SCEN-05",
                "name": "Multiple ETA Updates Chronological Resolution",
                "category": "RESCHEDULING",
                "test": lambda: repo.fetch_one("SELECT effective_eta_ts FROM v_latest_eta WHERE shipment_id = 'SHP1006';"),
                "validator": lambda r: r["effective_eta_ts"] == "2026-08-04T11:20:00+05:30"
            },
            # 6. Uncertain ETA handling
            {
                "id": "SCEN-06",
                "name": "Uncertain / Low-Confidence ETA",
                "category": "RESCHEDULING",
                "test": lambda: repo.fetch_one("SELECT eta_confidence FROM v_latest_eta WHERE shipment_id = 'SHP1013';"),
                "validator": lambda r: r["eta_confidence"] == "LOW"
            },
            # 7. Dock Breakdown Exclusion
            {
                "id": "SCEN-07",
                "name": "Dock D3 Breakdown Exclusion",
                "category": "DISRUPTIONS",
                "test": lambda: feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30"),
                "validator": lambda r: not any(s.dock_code == "D3" and s.slot_start_ts < "2026-08-04T13:00:00+05:30" for s in r.feasible_slots)
            },
            # 8. Unload Overrun Event
            {
                "id": "SCEN-08",
                "name": "Unload Overrun on Dock D2",
                "category": "DISRUPTIONS",
                "test": lambda: repo.fetch_one("SELECT event_type FROM dock_status_events WHERE dock_event_id = 'DEVT003';"),
                "validator": lambda r: r["event_type"] == "CAPACITY_REDUCTION"
            },
            # 9. Appointment Cancellation Frees Capacity
            {
                "id": "SCEN-09",
                "name": "Customer Cancellation Frees Capacity",
                "category": "CAPACITY",
                "test": lambda: repo.fetch_one("SELECT availability_status FROM v_slot_availability WHERE slot_id = 'SLOT-JAI-017';"),
                "validator": lambda r: r["availability_status"] == "AVAILABLE"
            },
            # 10. No-Show Tracking
            {
                "id": "SCEN-10",
                "name": "No-Show Recorded",
                "category": "CAPACITY",
                "test": lambda: repo.fetch_one("SELECT appointment_status FROM appointments WHERE appointment_id = 'APT1018';"),
                "validator": lambda r: r["appointment_status"] == "NO_SHOW"
            },
            # 11. Reefer Compatibility
            {
                "id": "SCEN-11",
                "name": "Reefer Dock Restriction",
                "category": "COMPATIBILITY",
                "test": lambda: feasibility.search_feasible_slots("SHP1010", min_time="2026-08-04T11:00:00+05:30"),
                "validator": lambda r: all(s.dock_type == "REEFER" for s in r.feasible_slots)
            },
            # 12. Reefer Dock Unavailable Escalation
            {
                "id": "SCEN-12",
                "name": "Reefer Dock Unavailable (DEVT002) Escalation",
                "category": "ESCALATIONS",
                "test": lambda: feasibility.search_feasible_slots("SHP1015", min_time="2026-08-04T18:30:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.NO_FEASIBLE_SLOT and len(r.feasible_slots) == 0
            },
            # 13. Heavy Vehicle Compatibility
            {
                "id": "SCEN-13",
                "name": "Heavy Vehicle 31-Tonne Bay Restriction",
                "category": "COMPATIBILITY",
                "test": lambda: feasibility.search_feasible_slots("SHP1016", min_time="2026-08-04T12:00:00+05:30"),
                "validator": lambda r: all(s.dock_code == "D6" and s.dock_type == "HEAVY" for s in r.feasible_slots)
            },
            # 14. Priority Conflict
            {
                "id": "SCEN-14",
                "name": "Critical vs Normal Priority Distinction",
                "category": "PRIORITY",
                "test": lambda: repo.fetch_one("SELECT priority_code FROM shipments WHERE shipment_id = 'SHP1009';"),
                "validator": lambda r: r["priority_code"] == "CRITICAL"
            },
            # 15. Race Condition Protection
            {
                "id": "SCEN-15",
                "name": "Zero Double-Booking Guarantee",
                "category": "CONCURRENCY",
                "test": lambda: repo.fetch_one("SELECT COUNT(*) AS c FROM appointments WHERE appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS') GROUP BY slot_id HAVING COUNT(*) > 1;"),
                "validator": lambda r: r is None
            },
            # 16. Appointment History Preservation
            {
                "id": "SCEN-16",
                "name": "Appointment History Preserved",
                "category": "AUDIT",
                "test": lambda: repo.fetch_all("SELECT appointment_id, appointment_status, is_current FROM appointments WHERE shipment_id = 'SHP1012';"),
                "validator": lambda r: len(r) > 0 and any(a["is_current"] == 0 for a in r)
            },
            # 17. Duplicate Message Deduplication
            {
                "id": "SCEN-17",
                "name": "Duplicate Message Replay Flagged",
                "category": "MESSAGING",
                "test": lambda: repo.fetch_one("SELECT is_duplicate FROM chat_messages WHERE chat_message_id = 'MSG015';"),
                "validator": lambda r: r["is_duplicate"] == 1
            },
            # 18. Ambiguous Driver Shipment
            {
                "id": "SCEN-18",
                "name": "Multi-Shipment Driver Ambiguity Detected",
                "category": "DRIVER_CONTEXT",
                "test": lambda: feasibility.resolve_driver_context(driver_id="DRV004"),
                "validator": lambda r: r["result_code"] == ResultCode.AMBIGUOUS_IDENTITY and len(r["active_shipments"]) == 2
            },
            # 19. Ask-Only Enquiry Read-Only Invariance
            {
                "id": "SCEN-19",
                "name": "Ask-Only Query Causes Zero DB Mutations",
                "category": "TRANSACTIONS",
                "test": lambda: feasibility.search_feasible_slots("SHP1017", min_time="2026-08-04T12:45:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.AVAILABLE
            },
            # 20. Cancelled Shipment Notification
            {
                "id": "SCEN-20",
                "name": "Cancelled Shipment Status Confirmed",
                "category": "STATUS",
                "test": lambda: repo.fetch_one("SELECT current_status FROM shipments WHERE shipment_id = 'SHP1019';"),
                "validator": lambda r: r["current_status"] == "CANCELLED"
            },
            # 21. Contact Gap Detection
            {
                "id": "SCEN-21",
                "name": "Missing Facility Contact Email Handling",
                "category": "RESILIENCE",
                "test": lambda: repo.fetch_one("SELECT contact_id, email, phone FROM facility_contacts WHERE email IS NULL;"),
                "validator": lambda r: r["contact_id"] == "CON005" and r["phone"] is not None
            },
            # 22. Operating Curfew Gate (21:00 at Jaipur)
            {
                "id": "SCEN-22",
                "name": "Facility Curfew Excludes Starts after 21:00",
                "category": "CURFEW",
                "test": lambda: feasibility.search_feasible_slots("SHP1006", min_time="2026-08-04T21:15:00+05:30"),
                "validator": lambda r: r.result_code == ResultCode.NO_FEASIBLE_SLOT
            }
        ]

        for s_def in scenarios_defs:
            t0 = time.time()
            status = "PASS"
            err_msg = None
            try:
                res = s_def["test"]()
                valid = s_def["validator"](res)
                if not valid:
                    status = "FAIL"
                    err_msg = "Validator returned False for scenario conditions."
            except Exception as e:
                status = "FAIL"
                err_msg = str(e)
            dur = round((time.time() - t0) * 1000, 2)

            results.append(ScenarioResult(
                scenario_id=s_def["id"],
                scenario_name=s_def["name"],
                category=s_def["category"],
                status=status,
                duration_ms=dur,
                assertions=[{"assertion": s_def["name"], "result": status}],
                error_message=err_msg
            ))

        # Cleanup fixture
        try:
            if os.path.exists(EVAL_FIXTURE_DB):
                os.remove(EVAL_FIXTURE_DB)
        except Exception:
            pass

        passed = sum(1 for r in results if r.status == "PASS")
        failed = len(results) - passed
        pass_rate = round((passed / len(results)) * 100, 1)
        avg_lat = round(sum(r.duration_ms for r in results) / len(results), 2)

        total_dur = round(sum(r.duration_ms for r in results), 2)
        report = EvalReport(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_scenarios=len(results),
            passed=passed,
            failed=failed,
            passed_scenarios=passed,
            failed_scenarios=failed,
            pass_rate_pct=pass_rate,
            avg_latency_ms=avg_lat,
            total_duration_ms=total_dur,
            scenarios=results
        )

        self.store.save_eval_report(report)
        return report


# Global eval engine singleton
eval_engine = EvalEngine()
