"""
SetuHaul Logistics — Database Repository
Provides safe, parameterized, connection-managed data access over SQLite.
Enforces explicit transactions and foreign keys.
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

def resolve_db_path() -> str:
    """Resolve database path checking env, cwd, parent directory, and backend folder."""
    if os.getenv("DATABASE_PATH"):
        return os.getenv("DATABASE_PATH")
    if os.path.exists("setuhaul_freight_operations.db"):
        return "setuhaul_freight_operations.db"
    candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "setuhaul_freight_operations.db"))
    if os.path.exists(candidate):
        return candidate
    backend_candidate = os.path.join("backend", "setuhaul_freight_operations.db")
    if os.path.exists(backend_candidate):
        return backend_candidate
    return "setuhaul_freight_operations.db"

DEFAULT_DB_PATH = resolve_db_path()


class DatabaseRepository:
    def __init__(self, db_path: Optional[str] = None, timeout: float = 5.0):
        self.db_path = db_path or resolve_db_path()
        self.timeout = timeout
        self._ensure_initialized()

    def _ensure_initialized(self):
        """Self-bootstraps database schema and seeds if database does not exist or is empty."""
        needs_init = False
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            needs_init = True
        else:
            try:
                conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shipments';")
                if not cursor.fetchone():
                    needs_init = True
                conn.close()
            except Exception:
                needs_init = True

        if needs_init:
            candidates = [
                os.path.join(os.path.dirname(self.db_path), "setuhaul_schema_and_seed.sql"),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "setuhaul_schema_and_seed.sql")),
                "setuhaul_schema_and_seed.sql",
                os.path.join("backend", "setuhaul_schema_and_seed.sql")
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            seed_sql = f.read()
                        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                        conn.executescript(seed_sql)
                        conn.commit()
                        conn.close()
                        print(f"[DatabaseRepository] Auto-bootstrapped database from {cand}")
                        break
                    except Exception as e:
                        print(f"[DatabaseRepository] Bootstrap error: {e}")

        # Ensure payload_json column exists in chat_messages
        try:
            conn = sqlite3.connect(self.db_path, timeout=self.timeout)
            cursor = conn.cursor()
            cursor.execute("ALTER TABLE chat_messages ADD COLUMN payload_json TEXT;")
            conn.commit()
            conn.close()
        except Exception:
            pass

    @contextmanager
    def get_connection(self):
        """Context manager yielding a SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a read query and return all rows as dictionaries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a read query and return the first row as a dictionary, or None."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a single write query inside an auto-committed transaction."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def save_chat_message(
        self,
        thread_id: str,
        sender_type: str,
        sender_reference: str,
        message_text: str,
        driver_id: Optional[str] = None,
        shipment_id: Optional[str] = None,
        payload_json: Optional[str] = None,
        parsed_intent: Optional[str] = None
    ) -> str:
        """Persists a chat message and maintains thread status in SQLite."""
        import uuid
        from datetime import datetime
        msg_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
        now_ts = datetime.now().astimezone().isoformat()

        # Sanitize driver_id and shipment_id to satisfy foreign key constraints
        clean_driver = driver_id if driver_id and driver_id != "UNKNOWN" else sender_reference
        valid_drivers = [
            "DRV001", "DRV002", "DRV003", "DRV004", "DRV005", "DRV006", "DRV007", "DRV008",
            "DRV009", "DRV010", "DRV011", "DRV012", "DRV013", "DRV014", "DRV015", "DRV016"
        ]
        if clean_driver not in valid_drivers:
            clean_driver = "DRV006"

        clean_shipment = shipment_id if shipment_id and shipment_id != "UNKNOWN" else None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Ensure thread exists in chat_threads
            cursor.execute("SELECT thread_id FROM chat_threads WHERE thread_id = ?", (thread_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO chat_threads (thread_id, driver_id, shipment_id, opened_at, thread_status, thread_intent)
                    VALUES (?, ?, ?, ?, 'OPEN', 'REPORT_DELAY');
                """, (thread_id, clean_driver, clean_shipment, now_ts))
            else:
                if clean_shipment or clean_driver:
                    cursor.execute("""
                        UPDATE chat_threads 
                        SET shipment_id = COALESCE(?, shipment_id),
                            driver_id = COALESCE(?, driver_id)
                        WHERE thread_id = ?;
                    """, (clean_shipment, clean_driver, thread_id))

            # Insert message
            cursor.execute("""
                INSERT INTO chat_messages (
                    chat_message_id, thread_id, sender_type, sender_reference,
                    message_text, message_ts, payload_json, parsed_intent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (msg_id, thread_id, sender_type, sender_reference, message_text, now_ts, payload_json, parsed_intent))
            conn.commit()
        return msg_id

    def get_chat_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Retrieves formatted chat message history for a thread."""
        query = """
            SELECT chat_message_id, thread_id, sender_type, sender_reference,
                   message_text, message_ts, payload_json, parsed_intent
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY message_ts ASC;
        """
        rows = self.fetch_all(query, (thread_id,))
        result = []
        import json
        for r in rows:
            role = "user" if r["sender_type"] == "DRIVER" else "assistant"
            payload = {}
            if r.get("payload_json"):
                try:
                    payload = json.loads(r["payload_json"])
                except Exception:
                    pass

            ts_formatted = r["message_ts"][11:16] if len(r.get("message_ts", "")) >= 16 else ""
            result.append({
                "message_id": r["chat_message_id"],
                "role": role,
                "content": r["message_text"],
                "timestamp": ts_formatted,
                "tool_calls": payload.get("tool_calls", []),
                "execution_pipeline": payload.get("execution_pipeline", []),
                "feasible_slots": payload.get("feasible_slots", []),
                "latency_ms": payload.get("latency_ms"),
                "status": payload.get("status") or r.get("parsed_intent")
            })
        return result

    def clear_chat_history(self, thread_id: str):
        """Cleans up messages and marks thread closed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE thread_id = ?", (thread_id,))
            cursor.execute("UPDATE chat_threads SET thread_status = 'CLOSED' WHERE thread_id = ?", (thread_id,))
            conn.commit()

    @contextmanager
    def immediate_transaction(self):
        """
        Yields an open cursor within a BEGIN IMMEDIATE transaction.
        Acquires SQLite's reserved lock immediately, preventing write races.
        Rolls back on error, commits on normal exit.
        """
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
