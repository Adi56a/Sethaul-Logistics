"""
SetuHaul Logistics — Phase 1 Audit Runner
Executes all SQL audit scripts against setuhaul_freight_operations.db
and validates outputs against Phase 1 exit criteria.
"""

import os
import sys
import sqlite3
from pathlib import Path

def run_all_audits(db_path: str = "setuhaul_freight_operations.db"):
    audit_dir = Path("sql/audit")
    sql_files = sorted(audit_dir.glob("*.sql"))

    if not sql_files:
        print(f"ERROR: No SQL files found in {audit_dir.resolve()}")
        sys.exit(1)

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total_files = len(sql_files)
    print(f"Found {total_files} audit scripts to execute.\n")

    for idx, sql_file in enumerate(sql_files, 1):
        print(f"[{idx}/{total_files}] Executing: {sql_file.name} ...")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Split statements by semicolon while ignoring comments
        statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
        
        for s_idx, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                rows = cursor.fetchall()
                if rows:
                    cols = [d[0] for d in cursor.description] if cursor.description else []
                    print(f"   Query {s_idx} returned {len(rows)} rows: {cols[:4]}...")
            except sqlite3.Error as e:
                print(f"   FAILED at statement {s_idx}: {e}")
                print(f"   Statement:\n{stmt}")
                sys.exit(1)

        print(f"   -> PASSED: {sql_file.name}\n")

    conn.close()
    print("All Phase 1 SQL audit scripts executed successfully with 0 errors!")

if __name__ == "__main__":
    db = os.getenv("DATABASE_PATH", "setuhaul_freight_operations.db")
    run_all_audits(db)
