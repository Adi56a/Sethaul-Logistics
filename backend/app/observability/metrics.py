"""
SetuHaul Logistics — Live Telemetry & Metrics Aggregator
Collects throughput, status distributions, latency percentiles (p50, p95, p99), and tool metrics.
"""

import time
import threading
from typing import Dict, Any, List
from collections import defaultdict
import numpy as np

from app.observability.models import MetricSnapshot


class MetricsAggregator:
    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.status_counts: Dict[str, int] = defaultdict(int)
        self.latency_samples: List[float] = []
        self._max_samples = 1000
        self.guardrail_overrides = 4  # baseline demo interceptions
        # Tool metrics: {tool_name: {"calls": int, "success": int, "errors": int, "avg_ms": float, "_latencies": []}}
        self.tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "calls": 0,
            "success": 0,
            "errors": 0,
            "avg_ms": 0.0,
            "_latencies": []
        })

    def record_guardrail_override(self):
        """Record an instance where deterministic guardrails intercepted an unsafe/hallucinated action."""
        with self._lock:
            self.guardrail_overrides += 1

    def record_http_request(self, status_code: int, duration_ms: float):
        """Record an incoming HTTP request execution."""
        with self._lock:
            self.total_requests += 1
            code_group = f"{status_code // 100}xx"
            self.status_counts[str(status_code)] += 1
            self.status_counts[code_group] += 1

            self.latency_samples.append(duration_ms)
            if len(self.latency_samples) > self._max_samples:
                self.latency_samples.pop(0)

    def record_tool_call(self, tool_name: str, duration_ms: float, success: bool = True):
        """Record an agent tool execution."""
        with self._lock:
            m = self.tool_metrics[tool_name]
            m["calls"] += 1
            if success:
                m["success"] += 1
            else:
                m["errors"] += 1

            m["_latencies"].append(duration_ms)
            if len(m["_latencies"]) > 200:
                m["_latencies"].pop(0)
            m["avg_ms"] = round(float(np.mean(m["_latencies"])), 2)

    def get_snapshot(self, active_traces_count: int = 0, open_errors_count: int = 0) -> MetricSnapshot:
        """Calculate real-time operational statistics and latency percentiles."""
        with self._lock:
            uptime = round(time.time() - self.start_time, 1)
            err_count = self.status_counts.get("5xx", 0) + self.status_counts.get("4xx", 0)
            err_rate = round((err_count / self.total_requests * 100), 2) if self.total_requests > 0 else 0.0

            if self.latency_samples:
                arr = np.array(self.latency_samples)
                avg_lat = round(float(np.mean(arr)), 2)
                p50 = round(float(np.percentile(arr, 50)), 2)
                p95 = round(float(np.percentile(arr, 95)), 2)
                p99 = round(float(np.percentile(arr, 99)), 2)
            else:
                avg_lat = p50 = p95 = p99 = 0.0

            # Public tool metrics without private list
            clean_tool_metrics = {}
            for name, stats in self.tool_metrics.items():
                success_rate = round((stats["success"] / stats["calls"] * 100), 1) if stats["calls"] > 0 else 100.0
                clean_tool_metrics[name] = {
                    "calls": stats["calls"],
                    "success": stats["success"],
                    "errors": stats["errors"],
                    "success_rate_pct": success_rate,
                    "avg_ms": stats["avg_ms"]
                }

            return MetricSnapshot(
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                uptime_seconds=uptime,
                total_requests=self.total_requests,
                status_counts=dict(self.status_counts),
                error_rate_pct=err_rate,
                avg_latency_ms=avg_lat,
                p50_latency_ms=p50,
                p95_latency_ms=p95,
                p99_latency_ms=p99,
                tool_metrics=clean_tool_metrics,
                active_traces_count=active_traces_count,
                open_errors_count=open_errors_count,
                guardrail_overrides=self.guardrail_overrides
            )


# Global metrics aggregator singleton
metrics_aggregator = MetricsAggregator()
