"""
SetuHaul Logistics — Distributed Tracer Engine
OpenTelemetry-compatible tracing with context propagation, nested span timing, and waterfall models.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from contextvars import ContextVar

from app.observability.models import SpanRecord, TraceRecord
from app.observability.store import ObservabilityStore

# Global context variables for thread/async-safe span propagation
_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("current_span_id", default=None)
_current_trace_spans: ContextVar[Optional[List[SpanRecord]]] = ContextVar("current_trace_spans", default=None)


class ActiveSpan:
    def __init__(self, tracer: 'Tracer', name: str, kind: str = "INTERNAL", attributes: Optional[Dict[str, Any]] = None):
        self.tracer = tracer
        self.name = name
        self.kind = kind
        self.attributes = attributes or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.status = "OK"
        self.span_id = uuid.uuid4().hex[:12]
        self.parent_span_id = _current_span_id.get()
        self.trace_id = _current_trace_id.get() or uuid.uuid4().hex[:16]

        self._prev_span_id = None
        self._prev_trace_id = None

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_error(self, error: Exception or str):
        self.status = "ERROR"
        self.attributes["error.message"] = str(error)

    def __enter__(self):
        self._prev_span_id = _current_span_id.get()
        self._prev_trace_id = _current_trace_id.get()

        _current_trace_id.set(self.trace_id)
        _current_span_id.set(self.span_id)

        spans_list = _current_trace_spans.get()
        if spans_list is None:
            spans_list = []
            _current_trace_spans.set(spans_list)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if exc_val:
            self.set_error(exc_val)

        record = SpanRecord(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            name=self.name,
            kind=self.kind,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_ms=self.duration_ms,
            status=self.status,
            attributes=self.attributes
        )

        spans_list = _current_trace_spans.get()
        if spans_list is not None:
            spans_list.append(record)

        # Restore context
        _current_span_id.set(self._prev_span_id)
        _current_trace_id.set(self._prev_trace_id)


class Tracer:
    def __init__(self, store: Optional[ObservabilityStore] = None):
        self.store = store or ObservabilityStore()

    def get_current_trace_id(self) -> Optional[str]:
        return _current_trace_id.get()

    @contextmanager
    def start_trace(self, root_name: str, kind: str = "HTTP_REQUEST", metadata: Optional[Dict[str, Any]] = None):
        """Starts a new top-level trace (e.g. for an incoming HTTP request)."""
        trace_id = uuid.uuid4().hex[:16]
        start_time = time.time()
        spans: List[SpanRecord] = []

        token_trace = _current_trace_id.set(trace_id)
        token_span = _current_span_id.set(None)
        token_spans = _current_trace_spans.set(spans)

        root_span = ActiveSpan(self, name=root_name, kind=kind, attributes=metadata or {})
        trace_status = "OK"

        try:
            with root_span:
                yield root_span
        except Exception as e:
            trace_status = "ERROR"
            raise e
        finally:
            end_time = time.time()
            duration_ms = round((end_time - start_time) * 1000, 2)

            if root_span.status == "ERROR":
                trace_status = "ERROR"

            trace_record = TraceRecord(
                trace_id=trace_id,
                root_span_name=root_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                status=trace_status,
                spans=spans,
                metadata=metadata or {}
            )

            self.store.save_trace(trace_record)

            _current_trace_id.reset(token_trace)
            _current_span_id.reset(token_span)
            _current_trace_spans.reset(token_spans)

    def span(self, name: str, kind: str = "INTERNAL", attributes: Optional[Dict[str, Any]] = None):
        """Context manager to trace a nested function, tool call, or DB query."""
        return ActiveSpan(self, name=name, kind=kind, attributes=attributes)


# Global tracer singleton
tracer = Tracer()
