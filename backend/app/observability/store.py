"""
SetuHaul Logistics — Observability Store
Persistent SQLite storage with fast in-memory indexing for Traces, Errors, and Evals.
"""

import os
import json
import sqlite3
import time
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from app.observability.models import (
    SpanRecord,
    TraceRecord,
    ErrorRecord,
    EvalReport,
    ScenarioResult
)
from app.repositories.db import resolve_db_path


class ObservabilityStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or resolve_db_path()
        # In-memory recent cache for instant sub-millisecond retrieval
        self._trace_cache: Dict[str, TraceRecord] = {}
        self._recent_trace_ids: List[str] = []
        self._max_cache = 200
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_tables(self):
        """Create observability schema tables if not exist."""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observability_traces (
                    trace_id TEXT PRIMARY KEY,
                    root_span_name TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_ms REAL,
                    status TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observability_spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_ms REAL,
                    status TEXT NOT NULL,
                    attributes_json TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (trace_id) REFERENCES observability_traces(trace_id)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observability_errors (
                    error_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    stack_trace TEXT,
                    endpoint TEXT,
                    context_json TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observability_eval_runs (
                    eval_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    total_scenarios INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    pass_rate_pct REAL NOT NULL,
                    avg_latency_ms REAL NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
            conn.commit()

    # --- Traces & Spans ---

    def save_trace(self, trace: TraceRecord):
        """Persist a completed trace and its spans."""
        # Update cache
        self._trace_cache[trace.trace_id] = trace
        if trace.trace_id not in self._recent_trace_ids:
            self._recent_trace_ids.append(trace.trace_id)
            if len(self._recent_trace_ids) > self._max_cache:
                oldest = self._recent_trace_ids.pop(0)
                self._trace_cache.pop(oldest, None)

        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO observability_traces 
                    (trace_id, root_span_name, start_time, end_time, duration_ms, status, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    trace.trace_id,
                    trace.root_span_name,
                    trace.start_time,
                    trace.end_time,
                    trace.duration_ms,
                    trace.status,
                    json.dumps(trace.metadata)
                ))

                for span in trace.spans:
                    conn.execute("""
                        INSERT OR REPLACE INTO observability_spans
                        (span_id, trace_id, parent_span_id, name, kind, start_time, end_time, duration_ms, status, attributes_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        span.span_id,
                        span.trace_id,
                        span.parent_span_id,
                        span.name,
                        span.kind,
                        span.start_time,
                        span.end_time,
                        span.duration_ms,
                        span.status,
                        json.dumps(span.attributes)
                    ))
                conn.commit()
        except Exception as e:
            # Fallback to cache without failing application request
            pass

    def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        """Fetch a trace with all child spans."""
        if trace_id in self._trace_cache:
            return self._trace_cache[trace_id]

        try:
            with self._conn() as conn:
                t_row = conn.execute("SELECT * FROM observability_traces WHERE trace_id = ?;", (trace_id,)).fetchone()
                if not t_row:
                    return None

                s_rows = conn.execute("""
                    SELECT * FROM observability_spans WHERE trace_id = ? ORDER BY start_time ASC;
                """, (trace_id,)).fetchall()

                spans = [
                    SpanRecord(
                        trace_id=r["trace_id"],
                        span_id=r["span_id"],
                        parent_span_id=r["parent_span_id"],
                        name=r["name"],
                        kind=r["kind"],
                        start_time=r["start_time"],
                        end_time=r["end_time"],
                        duration_ms=r["duration_ms"],
                        status=r["status"],
                        attributes=json.loads(r["attributes_json"] or "{}")
                    )
                    for r in s_rows
                ]

                trace = TraceRecord(
                    trace_id=t_row["trace_id"],
                    root_span_name=t_row["root_span_name"],
                    start_time=t_row["start_time"],
                    end_time=t_row["end_time"],
                    duration_ms=t_row["duration_ms"],
                    status=t_row["status"],
                    metadata=json.loads(t_row["metadata_json"] or "{}"),
                    spans=spans
                )
                self._trace_cache[trace_id] = trace
                return trace
        except Exception:
            return None

    def list_traces(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recent traces for the dashboard."""
        try:
            with self._conn() as conn:
                query = "SELECT * FROM observability_traces"
                params = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY start_time DESC LIMIT ?;"
                params.append(limit)

                rows = conn.execute(query, params).fetchall()
                results = []
                for r in rows:
                    span_count_row = conn.execute(
                        "SELECT COUNT(*) as c FROM observability_spans WHERE trace_id = ?;", 
                        (r["trace_id"],)
                    ).fetchone()
                    results.append({
                        "trace_id": r["trace_id"],
                        "root_span_name": r["root_span_name"],
                        "start_time": r["start_time"],
                        "formatted_time": time.strftime("%H:%M:%S", time.localtime(r["start_time"])),
                        "duration_ms": r["duration_ms"],
                        "status": r["status"],
                        "span_count": span_count_row["c"] if span_count_row else 1,
                        "metadata": json.loads(r["metadata_json"] or "{}")
                    })
                return results
        except Exception:
            return []

    # --- Error Logs ---

    def record_error(self, error: ErrorRecord):
        """Save a tracked error."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO observability_errors
                    (error_id, timestamp, severity, error_type, message, stack_trace, endpoint, context_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    error.error_id,
                    error.timestamp,
                    error.severity,
                    error.error_type,
                    error.message,
                    error.stack_trace,
                    error.endpoint,
                    json.dumps(error.context),
                    error.status
                ))
                conn.commit()
        except Exception:
            pass

    def list_errors(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tracked errors."""
        try:
            with self._conn() as conn:
                query = "SELECT * FROM observability_errors"
                params = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY timestamp DESC LIMIT ?;"
                params.append(limit)

                rows = conn.execute(query, params).fetchall()
                return [
                    {
                        "error_id": r["error_id"],
                        "timestamp": r["timestamp"],
                        "severity": r["severity"],
                        "error_type": r["error_type"],
                        "message": r["message"],
                        "stack_trace": r["stack_trace"],
                        "endpoint": r["endpoint"],
                        "context": json.loads(r["context_json"] or "{}"),
                        "status": r["status"]
                    }
                    for r in rows
                ]
        except Exception:
            return []

    def resolve_error(self, error_id: str) -> bool:
        """Mark an error as resolved."""
        try:
            with self._conn() as conn:
                conn.execute("UPDATE observability_errors SET status = 'RESOLVED' WHERE error_id = ?;", (error_id,))
                conn.commit()
                return True
        except Exception:
            return False

    # --- Evals ---

    def save_eval_report(self, report: EvalReport):
        """Save an evaluation run result."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO observability_eval_runs
                    (eval_id, timestamp, total_scenarios, passed, failed, pass_rate_pct, avg_latency_ms, report_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    report.eval_id,
                    report.timestamp,
                    report.total_scenarios,
                    report.passed,
                    report.failed,
                    report.pass_rate_pct,
                    report.avg_latency_ms,
                    report.model_dump_json()
                ))
                conn.commit()
        except Exception:
            pass

    def list_eval_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List past evaluation reports."""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT eval_id, timestamp, total_scenarios, passed, failed, pass_rate_pct, avg_latency_ms 
                    FROM observability_eval_runs 
                    ORDER BY timestamp DESC LIMIT ?;
                """, (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def get_eval_report(self, eval_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full scenario report for an evaluation run."""
        try:
            with self._conn() as conn:
                row = conn.execute("SELECT report_json FROM observability_eval_runs WHERE eval_id = ?;", (eval_id,)).fetchone()
                if row:
                    return json.loads(row["report_json"])
                return None
        except Exception:
            return None
