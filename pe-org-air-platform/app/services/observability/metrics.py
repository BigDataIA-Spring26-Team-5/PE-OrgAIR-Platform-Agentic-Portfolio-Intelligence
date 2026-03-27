"""Prometheus metrics and instrumentation decorators for CS5.

Metrics are pre-initialized with all known label combinations so they
appear in /metrics immediately (not just after the first call).
"""
from __future__ import annotations

import functools
import time
import logging
from typing import Callable, Any

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Known label combinations for pre-initialization
_MCP_TOOLS = [
    "calculate_org_air_score", "get_company_evidence", "generate_justification",
    "project_ebitda_impact", "run_gap_analysis", "get_portfolio_summary",
]
_AGENTS = ["sec_analyst", "scorer", "evidence_agent", "value_creator", "supervisor"]
_CS_SERVICES = [("cs1", "/portfolio"), ("cs2", "/evidence"), ("cs3", "/scores"), ("cs4", "/justify")]

# ── MCP Tool Metrics ─────────────────────────────────────────────────────────

mcp_tool_calls_total = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    ["tool_name", "status"],
)

mcp_tool_duration_seconds = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool call duration in seconds",
    ["tool_name"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── Agent Metrics ────────────────────────────────────────────────────────────

agent_invocations_total = Counter(
    "agent_invocations_total",
    "Total agent node invocations",
    ["agent_name", "status"],
)

agent_duration_seconds = Histogram(
    "agent_duration_seconds",
    "Agent node execution duration in seconds",
    ["agent_name"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ── HITL Metrics ─────────────────────────────────────────────────────────────

hitl_approvals_total = Counter(
    "hitl_approvals_total",
    "Total HITL approval decisions",
    ["reason", "decision"],
)

# ── CS Client Metrics ────────────────────────────────────────────────────────

cs_client_calls_total = Counter(
    "cs_client_calls_total",
    "Total CS client service calls",
    ["service", "endpoint", "status"],
)


# ── Pre-initialize all label combinations so /metrics shows them ──────────
def _init_metrics():
    for tool in _MCP_TOOLS:
        mcp_tool_calls_total.labels(tool_name=tool, status="success")
        mcp_tool_calls_total.labels(tool_name=tool, status="error")
        mcp_tool_duration_seconds.labels(tool_name=tool)
    for agent in _AGENTS:
        agent_invocations_total.labels(agent_name=agent, status="success")
        agent_invocations_total.labels(agent_name=agent, status="error")
        agent_duration_seconds.labels(agent_name=agent)
    hitl_approvals_total.labels(reason="score_change", decision="approved")
    hitl_approvals_total.labels(reason="score_change", decision="rejected")
    for svc, ep in _CS_SERVICES:
        cs_client_calls_total.labels(service=svc, endpoint=ep, status="success")
        cs_client_calls_total.labels(service=svc, endpoint=ep, status="error")

_init_metrics()


# ── Decorators ───────────────────────────────────────────────────────────────

def track_mcp_tool(tool_name: str) -> Callable:
    """Decorator to instrument async MCP tool functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                mcp_tool_calls_total.labels(tool_name=tool_name, status="success").inc()
                return result
            except Exception as e:
                mcp_tool_calls_total.labels(tool_name=tool_name, status="error").inc()
                raise
            finally:
                duration = time.time() - start
                mcp_tool_duration_seconds.labels(tool_name=tool_name).observe(duration)
        return wrapper
    return decorator


def track_agent(agent_name: str) -> Callable:
    """Decorator to instrument agent node functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                agent_invocations_total.labels(agent_name=agent_name, status="success").inc()
                return result
            except Exception as e:
                agent_invocations_total.labels(agent_name=agent_name, status="error").inc()
                raise
            finally:
                duration = time.time() - start
                agent_duration_seconds.labels(agent_name=agent_name).observe(duration)
        return wrapper
    return decorator


def track_cs_client(service: str, endpoint: str) -> Callable:
    """Decorator to instrument CS client calls."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = func(*args, **kwargs)
                cs_client_calls_total.labels(
                    service=service, endpoint=endpoint, status="success"
                ).inc()
                return result
            except Exception as e:
                cs_client_calls_total.labels(
                    service=service, endpoint=endpoint, status="error"
                ).inc()
                raise
        return wrapper
    return decorator
