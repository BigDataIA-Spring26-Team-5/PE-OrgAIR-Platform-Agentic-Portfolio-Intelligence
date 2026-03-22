"""Agentic Due Diligence — Complete Multi-Agent Workflow.

Runs the full LangGraph due-diligence graph for a portfolio company
and prints a structured summary of results.

Usage:
    python exercises/agentic_due_diligence.py
"""
import sys
import os

# Ensure project root is on sys.path regardless of where the script is invoked from
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from datetime import datetime

from app.agents.supervisor import dd_graph
from app.agents.state import DueDiligenceState


async def run_due_diligence(
    company_id: str = "NVDA",
    assessment_type: str = "full",
) -> DueDiligenceState:
    """Run the complete due-diligence LangGraph workflow for a company.

    Args:
        company_id: Portfolio company ticker (e.g. "NVDA", "JPM").
        assessment_type: "screening" | "limited" | "full"

    Returns:
        Final DueDiligenceState after all agents have run.
    """
    initial_state: DueDiligenceState = {
        "company_id": company_id,
        "assessment_type": assessment_type,
        "requested_by": "analyst",
        "messages": [],
        "sec_analysis": None,
        "talent_analysis": None,
        "scoring_result": None,
        "evidence_justifications": None,
        "value_creation_plan": None,
        "next_agent": None,
        "requires_approval": False,
        "approval_reason": None,
        "approval_status": None,
        "approved_by": None,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "total_tokens": 0,
        "error": None,
    }

    config = {
        "configurable": {
            "thread_id": f"dd-{company_id}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        }
    }

    return await dd_graph.ainvoke(initial_state, config)


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Agentic Due Diligence Workflow")
    parser.add_argument("ticker", nargs="?", default="NVDA",
                        help="Company ticker (default: NVDA). Any ticker in your Snowflake companies table.")
    parser.add_argument("--type", default="full", choices=["screening", "limited", "full"],
                        help="Assessment type (default: full)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"PE Org-AI-R Platform: Agentic Due Diligence")
    print(f"Company: {args.ticker.upper()}  |  Type: {args.type}")
    print("=" * 60)

    result = await run_due_diligence(args.ticker.upper(), args.type)

    # ── Scoring results ───────────────────────────────────────────────────────
    scoring = result.get("scoring_result") or {}
    org_air = scoring.get("org_air", 0.0)
    vr = scoring.get("vr_score", 0.0)
    hr = scoring.get("hr_score", 0.0)

    print(f"\nOrg-AI-R Score : {org_air:.1f}")
    print(f"V^R Score      : {vr:.1f}")
    print(f"H^R Score      : {hr:.1f}")

    dim_scores = scoring.get("dimension_scores", {})
    if dim_scores:
        print("\nDimension Scores:")
        for dim, score in dim_scores.items():
            print(f"  {dim:<25} {score:.1f}")

    # ── HITL status ───────────────────────────────────────────────────────────
    print(f"\nHITL Required  : {result.get('requires_approval', False)}")
    print(f"Approval Status: {result.get('approval_status', 'N/A')}")
    print(f"Approved By    : {result.get('approved_by', 'N/A')}")
    if result.get("approval_reason"):
        print(f"Approval Reason: {result['approval_reason']}")

    # ── Value creation ────────────────────────────────────────────────────────
    plan = result.get("value_creation_plan") or {}
    if plan:
        print(f"\nEBITDA Impact  : {plan.get('risk_adjusted', 'N/A')}")
        scenarios = plan.get("scenarios", {})
        if scenarios:
            print(f"  Conservative : {scenarios.get('conservative', 'N/A')}")
            print(f"  Base Case    : {scenarios.get('base', 'N/A')}")
            print(f"  Optimistic   : {scenarios.get('optimistic', 'N/A')}")

    # ── Message log ───────────────────────────────────────────────────────────
    messages = result.get("messages", [])
    print(f"\nMessages logged: {len(messages)}")
    for msg in messages:
        agent = getattr(msg, "agent_name", None) or msg.get("agent_name", "?")
        content = str(getattr(msg, "content", None) or msg.get("content", ""))
        # Print first 300 chars so narrative is readable but not overwhelming
        preview = content[:300] + ("..." if len(content) > 300 else "")
        print(f"\n  [{agent}]")
        print(f"  {preview}")

    # ── Completion ────────────────────────────────────────────────────────────
    completed_at = result.get("completed_at")
    if completed_at:
        print(f"\nCompleted at: {completed_at}")
    if result.get("error"):
        print(f"\nError: {result['error']}")

    print("\n" + "=" * 60)
    print("All data sourced from CS1-CS4 via MCP tools (no mock data).")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
