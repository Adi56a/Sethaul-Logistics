"""
SetuHaul Logistics — Error Monitoring Engine
Captures, categorizes, and tracks errors across API, DB, Agent, and Business Logic.
"""

import time
import traceback
from typing import Dict, Any, Optional

from app.observability.models import ErrorRecord
from app.observability.store import ObservabilityStore


class ErrorMonitor:
    def __init__(self, store: Optional[ObservabilityStore] = None):
        self.store = store or ObservabilityStore()

    def capture_exception(
        self,
        exc: Exception,
        endpoint: Optional[str] = None,
        severity: str = "ERROR",
        error_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        """Captures an exception with stack trace and context."""
        tb_str = traceback.format_exc()
        if not error_type:
            error_type = exc.__class__.__name__

        record = ErrorRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            severity=severity,
            error_type=error_type,
            message=str(exc),
            stack_trace=tb_str,
            endpoint=endpoint,
            context=context or {},
            status="OPEN"
        )

        self.store.record_error(record)
        return record

    def capture_error(
        self,
        message: str,
        error_type: str = "BUSINESS_RULE_VIOLATION",
        severity: str = "WARNING",
        endpoint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        """Captures an operational error or constraint violation."""
        record = ErrorRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            severity=severity,
            error_type=error_type,
            message=message,
            stack_trace=None,
            endpoint=endpoint,
            context=context or {},
            status="OPEN"
        )
        self.store.record_error(record)
        return record

    def resolve_error(self, error_id: str) -> bool:
        """Resolves an error in the audit log."""
        return self.store.resolve_error(error_id)

    def list_errors(self, limit: int = 50, status: Optional[str] = None):
        return self.store.list_errors(limit=limit, status=status)


# Global error monitor singleton
error_monitor = ErrorMonitor()
