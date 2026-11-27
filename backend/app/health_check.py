"""
SetuHaul Logistics — System & Database Health Check
Verifies environment, database integrity, schema objects, constraints, and views.
"""

import os
import sys
import sqlite3
from typing import Dict, Any, List

def run_health_check(db_path: str = "setuhaul_freight_operations.db") -> Dict[str, Any]:
    report = {
        "status": "PASS",
        "db_path": db_path,
        "checks": {}
    }

    # 1. Check DB file exists
    if not os.path.exists(db_path):
        report["status"] = "FAIL"
        report["checks"]["file_exists"] = f"Database file not found at: {db_path}"
        return report
    report["checks"]["file_exists"] = True

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()

        # 2. PRAGMA integrity_check
        c.execute("PRAGMA integrity_check;")
        integrity = c.fetchone()[0]
        if integrity != "ok":
            report["status"] = "FAIL"
            report["checks"]["integrity_check"] = integrity
        else:
            report["checks"]["integrity_check"] = "ok"

        # 3. PRAGMA foreign_key_check
        c.execute("PRAGMA foreign_key_check;")
        fk_violations = c.fetchall()
        if fk_violations:
            report["status"] = "FAIL"
            report["checks"]["foreign_keys"] = f"{len(fk_violations)} violations found"
        else:
            report["checks"]["foreign_keys"] = "0 violations"

        # 4. Required tables check
        expected_tables = {
            "carriers": 4,
            "drivers": 15,
            "vehicle_types": 5,
            "vehicles": 15,
            "facilities": 2,
            "docks": 9,
            "facility_contacts": 5,
            "facility_rules": 6,
            "shipments": 21,
            "eta_updates": 12,
            "appointment_slots": 106,
            "appointments": 20,
            "dock_status_events": 3,
            "facility_checkins": 5,
            "chat_threads": 12,
            "chat_messages": 20,
            "driver_exceptions": 10,
            "operational_messages": 5
        }

        table_counts = {}
        for table, expected_min in expected_tables.items():
            c.execute(f"SELECT COUNT(*) FROM {table};")
            count = c.fetchone()[0]
            table_counts[table] = count
            if count < expected_min:
                report["status"] = "WARN"
        report["checks"]["tables"] = table_counts

        # 5. Required views check
        expected_views = [
            "v_latest_eta",
            "v_slot_availability",
            "v_inbound_operational_state",
            "v_current_facility_queue"
        ]
        view_status = {}
        for view in expected_views:
            c.execute(f"SELECT COUNT(*) FROM {view};")
            view_status[view] = f"{c.fetchone()[0]} rows"
        report["checks"]["views"] = view_status

        # 6. Concurrency partial unique indexes check
        c.execute("""
            SELECT name FROM sqlite_master 
            WHERE type = 'index' AND name IN (
                'ux_active_appointment_per_slot',
                'ux_current_active_appointment_per_shipment'
            );
        """)
        found_indexes = [r[0] for r in c.fetchall()]
        if len(found_indexes) != 2:
            report["status"] = "FAIL"
            report["checks"]["indexes"] = f"Missing unique indexes. Found: {found_indexes}"
        else:
            report["checks"]["indexes"] = "Partial unique indexes verified"

        conn.close()

    except Exception as e:
        report["status"] = "FAIL"
        report["checks"]["exception"] = str(e)

    return report


if __name__ == "__main__":
    db = os.getenv("DATABASE_PATH", "setuhaul_freight_operations.db")
    print(f"Running SetuHaul Health Check against: {db} ...")
    res = run_health_check(db)
    
    print("\n================ HEALTH CHECK SUMMARY ================")
    print(f"Overall Status: {res['status']}")
    for k, v in res["checks"].items():
        if isinstance(v, dict):
            print(f"- {k}: {len(v)} objects verified")
        else:
            print(f"- {k}: {v}")
    print("======================================================\n")

    if res["status"] == "FAIL":
        sys.exit(1)
    sys.exit(0)
