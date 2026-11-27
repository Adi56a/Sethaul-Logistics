"""
SetuHaul Logistics — Observability Data Models
Typed models for Distributed Traces, Spans, Metrics, Error Tracking, and Evals.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time
import uuid


class SpanRecord(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    kind: str = "INTERNAL"  # HTTP_REQUEST, AGENT_TURN, TOOL_CALL, DB_QUERY, FEASIBILITY_CHECK, EVAL_RUN
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "OK"  # OK, ERROR, WARNING
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TraceRecord(BaseModel):
    trace_id: str
    root_span_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "OK"  # OK, ERROR
    spans: List[SpanRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorRecord(BaseModel):
    error_id: str = Field(default_factory=lambda: f"ERR-{uuid.uuid4().hex[:8].upper()}")
    timestamp: str
    severity: str = "ERROR"  # CRITICAL, ERROR, WARNING, INFO
    error_type: str  # DATABASE_ERROR, CONFLICT, VALIDATION_ERROR, LLM_ERROR, RULE_VIOLATION
    message: str
    stack_trace: Optional[str] = None
    endpoint: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    status: str = "OPEN"  # OPEN, RESOLVED, IGNORED


class MetricSnapshot(BaseModel):
    timestamp: str
    uptime_seconds: float
    total_requests: int
    status_counts: Dict[str, int]
    error_rate_pct: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    tool_metrics: Dict[str, Dict[str, Any]]
    active_traces_count: int
    open_errors_count: int


class ScenarioResult(BaseModel):
    scenario_id: str
    scenario_name: str
    category: str
    status: str  # PASS, FAIL
    duration_ms: float
    assertions: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


class EvalReport(BaseModel):
    eval_id: str = Field(default_factory=lambda: f"EVAL-{uuid.uuid4().hex[:8].upper()}")
    timestamp: str
    total_scenarios: int
    passed: int
    failed: int
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    pass_rate_pct: float
    avg_latency_ms: float
    total_duration_ms: float = 0.0
    scenarios: List[ScenarioResult] = Field(default_factory=list)
