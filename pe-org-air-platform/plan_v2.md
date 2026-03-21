# CS5: Agentic Portfolio Intelligence — Implementation Record (v2)

> **Purpose:** Documents exactly what was built for Steps 6–10, with file paths, class/function names, design decisions, and how each piece connects. Use this as the reference for the remaining phases (5, 6, 10).

---

## Execution Status

| Step | Phase | Task | Pts | Status |
|------|-------|------|-----|--------|
| 6 | 2 | MCP Server Core (6 tools) | 12 | DONE |
| 7 | 3 | MCP Resources & Prompts | 8 | DONE |
| 8 | 7 | LangGraph State | 8 | DONE |
| 9 | 8 | Specialist Agents | 12 | DONE |
| 10 | 9 | Supervisor + HITL | 10 | DONE |
| 11 | 5 | Evidence Display Component | 6 | **TODO** |
| 12 | 6 | Portfolio Dashboard (cs5_app.py) | 10 | **TODO** |
| 13 | 10 | DD Workflow Exercise | 10 | **TODO** |

**Done: 74 pts | Remaining: 26 pts**

---

## Step 6 — MCP Server Core (Phase 2, 12 pts)

**File:** `app/mcp/server.py`
**Entry point:** `poetry run python -m app.mcp.server` (stdio transport)

### Design decisions
- **No app-level imports at module level** — `app/services/__init__.py` eagerly imports Redis via `cache.py`, which breaks standalone MCP startup. All service imports are deferred inside lazy singleton functions (`_ebitda()`, `_gap()`, `_cs3()`, `_cs2()`, `_cs4()`).
- **Sync httpx inside `asyncio.to_thread`** — MCP tools that call FastAPI use `httpx.Client(timeout=None)` wrapped in `asyncio.to_thread`. This avoids `ReadTimeout` errors that occurred with `httpx.AsyncClient` in the MCP subprocess context.
- **`call_tool` returns `{"error": ...}` on exception** — re-raising caused the MCP client to receive an empty response. Returning a structured error dict keeps the JSON-RPC channel intact.
- **Prometheus metrics** — every tool call records to `mcp_tool_calls_total` and `mcp_tool_duration_seconds` via `_track()`. Silently skips if `app.services.observability.metrics` is unavailable.

### 6 Tools

| # | Tool name | Backend | Returns |
|---|-----------|---------|---------|
| 1 | `calculate_org_air_score` | `CompositeScoringRepository._query()` → SCORING table | `company_id, org_air, vr_score, hr_score, synergy_score, confidence_interval, dimension_scores` |
| 2 | `get_company_evidence` | `FastAPI GET /api/v1/rag/evidence/{ticker}` | `{"evidence": [...], "count": N}` |
| 3 | `generate_justification` | `FastAPI GET /api/v1/rag/justify/{ticker}/{dimension}` | `dimension, score, level, level_name, evidence_strength, rubric_criteria, supporting_evidence, gaps_identified` |
| 4 | `project_ebitda_impact` | `EBITDACalculator.project()` — pure local math | `delta_air, scenarios {conservative/base/optimistic}, risk_adjusted, requires_approval` |
| 5 | `run_gap_analysis` | `CS3Client` + `GapAnalyzer.analyze()` | `GapAnalysisResult.to_dict()` |
| 6 | `get_portfolio_summary` | `CS3Client` iteration over `CS3_PORTFOLIO` | `fund_id, fund_air, company_count, companies [{ticker, org_air, sector}]` |

### Key runtime fix: Snowflake key casing
`CompositeScoringRepository._query()` uses Snowflake's `DictCursor` which returns **uppercase** column names (`ORG_AIR`, `VR_SCORE`). All reads immediately normalise with `{k.lower(): v for k, v in row.items()}` before accessing values.

### Test file
`app/mcp/test_mcp.py` — interactive menu (options 1–6, r1–r3, p1–p3). Run with:
```bash
poetry run python -m app.mcp.test_mcp
```

---

## Step 7 — MCP Resources & Prompts (Phase 3, 8 pts)

**File:** `app/mcp/server.py` (additional handlers appended to same file)

### Resources

| URI | Contents |
|-----|----------|
| `orgair://parameters/v2.0` | `ALPHA_VR_WEIGHT`, `BETA_SYNERGY_WEIGHT`, `LAMBDA_PENALTY`, `DELTA_POSITION`, all 7 dimension weights, `HITL_SCORE_CHANGE_THRESHOLD`, `HITL_EBITDA_PROJECTION_THRESHOLD` — all read live from `app/core/settings.py` |
| `orgair://sectors` | Per-company sector, EBITDA multiplier, implementation cost factor; sector baselines (h_r_base, key weight dimension) |

**Key fix:** MCP SDK passes the URI as a Pydantic `AnyUrl` object (not a plain string). `AnyUrl` adds a trailing slash to bare hostnames (`orgair://sectors` → `orgair://sectors/`). Fixed with:
```python
uri = str(uri).rstrip("/")
```

### Prompts

| Name | Purpose |
|------|---------|
| `due_diligence_assessment` | Instructs agent: get assessment → get evidence → generate justifications → run gap analysis → project EBITDA |
| `ic_meeting_prep` | IC meeting package: portfolio summary → company deep dive → risk flags → value creation plan |

Both prompts accept `company_id` as a required argument and return a `GetPromptResult` with a single user `PromptMessage`.

---

## Step 8 — LangGraph State (Phase 7, 8 pts)

**Files:** `app/agents/__init__.py`, `app/agents/state.py`

### `AgentMessage` (TypedDict)
```
role        : Literal["user", "assistant", "system", "tool"]
content     : str
agent_name  : Optional[str]   # which specialist produced this
timestamp   : datetime
```

### `DueDiligenceState` (TypedDict)

| Field | Type | Written by | CS layer |
|-------|------|-----------|---------|
| `company_id` | `str` | Supervisor init | Input |
| `assessment_type` | `Literal["screening","limited","full"]` | Supervisor init | Input |
| `requested_by` | `str` | Supervisor init | Input |
| `messages` | `Annotated[List[AgentMessage], operator.add]` | Every agent (append-only) | All |
| `sec_analysis` | `Optional[Dict]` | `SECAnalysisAgent` | CS2 |
| `talent_analysis` | `Optional[Dict]` | `EvidenceAgent` | CS2 talent |
| `scoring_result` | `Optional[Dict]` | `ScoringAgent` | CS3 |
| `evidence_justifications` | `Optional[Dict]` | Future justification agent | CS4 |
| `value_creation_plan` | `Optional[Dict]` | `ValueCreationAgent` | CS5 |
| `next_agent` | `Optional[str]` | Supervisor | Control |
| `requires_approval` | `bool` | `ScoringAgent`, `ValueCreationAgent` | HITL |
| `approval_reason` | `Optional[str]` | `ScoringAgent`, `ValueCreationAgent` | HITL |
| `approval_status` | `Optional[Literal["pending","approved","rejected"]]` | Supervisor, `hitl_approval_node` | HITL |
| `approved_by` | `Optional[str]` | `hitl_approval_node` | HITL |
| `started_at` | `datetime` | Supervisor init | Metadata |
| `completed_at` | `Optional[datetime]` | `complete_node` | Metadata |
| `total_tokens` | `int` | Reserved for cost tracking | Metadata |
| `error` | `Optional[str]` | Any agent on unhandled exception | Metadata |

The `operator.add` reducer on `messages` means every node appends its messages without overwriting prior history.

---

## Step 9 — Specialist Agents (Phase 8, 12 pts)

**Files:** `app/agents/specialists.py`, `app/agents/test_specialists.py`

### `MCPToolCaller`
Thin wrapper that mirrors the MCP server's tool implementations. Uses `httpx.Client(timeout=None)` + lazy singletons. Key routing decisions:

| Tool method | Backend | Why not HTTP endpoint |
|-------------|---------|----------------------|
| `calculate_org_air_score` | `CompositeScoringRepository._query()` directly | `/api/v1/assessments/{ticker}` returned zeros — Snowflake uppercase key bug |
| `get_company_evidence` | `FastAPI GET /api/v1/rag/evidence/{ticker}` | Has a proper endpoint |
| `generate_justification` | `FastAPI GET /api/v1/rag/justify/{ticker}/{dimension}` | Has a proper endpoint |
| `project_ebitda_impact` | `EBITDACalculator.project()` local | Pure math, no HTTP needed |
| `run_gap_analysis` | `CompositeScoringRepository._query()` + `GapAnalyzer` | No `/gap-analysis` REST endpoint exists |
| `get_portfolio_summary` | `CS3Client` iteration | No portfolio REST endpoint exists |

### 4 Specialist Agents

**`SECAnalysisAgent`**
- Reads: `company_id`
- Calls: `MCPToolCaller.get_company_evidence(limit=10)`
- LLM task: `"evidence_extraction"` → Groq llama-3.1-8b (free)
- Writes: `state["sec_analysis"]` = `{company_id, evidence_count, evidence, llm_summary}`

**`ScoringAgent`**
- Reads: `company_id`
- Calls: `MCPToolCaller.calculate_org_air_score()`
- HITL: sets `requires_approval=True` when `org_air >= hitl_score_change_threshold` (from `app/config`)
- Writes: `state["scoring_result"]` = `{company_id, org_air, vr_score, hr_score, synergy_score, ...}`

**`EvidenceAgent`** (talent dimension specialist)
- Reads: `company_id`
- Calls: `MCPToolCaller.get_company_evidence(dimension="talent", limit=10)`
- Filters evidence to `signal_category == "technology_hiring"`
- LLM task: `"evidence_extraction"` → Groq llama-3.1-8b (free)
- Writes: `state["talent_analysis"]` = `{company_id, evidence, technology_hiring_signals, llm_summary}`

**`ValueCreationAgent`**
- Reads: `company_id`, `scoring_result`
- Calls: `MCPToolCaller.run_gap_analysis()` + `MCPToolCaller.project_ebitda_impact()`
- HITL: sets `requires_approval=True` when `|risk_adjusted_ebitda| >= hitl_ebitda_threshold`
- LLM task: `"ic_summary"` → Claude Haiku (quality), falls back to Groq 70b
- Writes: `state["value_creation_plan"]` = `{gap_analysis, ebitda_projection, narrative, delta_air, scenarios, risk_adjusted, requires_approval}`

### LLM routing (via `ModelRouter.complete_sync`)
```
evidence_extraction  →  groq/llama-3.1-8b-instant   (free)
ic_summary           →  claude-haiku-4-5-20251001    ($0.25/$1.25 per MTok)
                     →  groq/llama-3.3-70b-versatile (fallback if no ANTHROPIC_API_KEY)
```

### Test
```bash
poetry run uvicorn app.main:app --reload   # Terminal 1
poetry run python -m app.agents.test_specialists   # Terminal 2
```

---

## Step 10 — Supervisor + HITL (Phase 9, 10 pts)

**Files:** `app/agents/supervisor.py`, `app/agents/test_supervisor.py`

### Graph structure
```
START → supervisor (conditional router)
supervisor → sec_analyst    → supervisor
supervisor → scorer         → supervisor
supervisor → evidence_agent → supervisor
supervisor → value_creator  → supervisor
supervisor → hitl_approval  → supervisor
supervisor → complete       → END
```
Compiled with `MemorySaver()` checkpointer for conversation thread persistence.

### `supervisor_node` routing logic
1. If `requires_approval=True` and `approval_status == "rejected"` → route to `complete` with error
2. If `requires_approval=True` and status not `"approved"` → set `approval_status="pending"`, route to `hitl_approval`
3. If `sec_analysis` missing → `sec_analyst`
4. If `scoring_result` missing → `scorer`
5. If `talent_analysis` missing → `evidence_agent`
6. If `value_creation_plan` missing and `assessment_type != "screening"` → `value_creator`
7. Else → `complete`

### Why `asyncio.to_thread`
Specialist agents use `ModelRouter.complete_sync()` and `httpx.Client` (both synchronous). LangGraph nodes are `async`. Wrapping with `asyncio.to_thread` runs the sync code in a thread pool without blocking the event loop.

### `hitl_approval_node`
- Logs the approval reason via structlog warning
- **Exercise mode:** auto-approves, sets `approval_status="approved"`, `approved_by="exercise_auto_approve"`, resets `requires_approval=False`
- **Production:** replace the return block with Slack/email notification + blocking wait
- Critical: must reset `requires_approval=False` so the supervisor loop continues past the gate

### HITL thresholds (from `app/config`)
```python
HITL_SCORE_CHANGE_THRESHOLD     = 15.0   # ScoringAgent triggers when org_air >= this
HITL_EBITDA_PROJECTION_THRESHOLD = 10.0  # ValueCreationAgent triggers when |risk_adjusted| >= this
```
NVDA's org_air of 84.94 reliably triggers the HITL gate in the test run.

### Verified test output (NVDA, full)
```
supervisor → sec_analyst → supervisor → scorer → [HITL triggered]
supervisor → hitl_approval → supervisor → evidence_agent → supervisor
supervisor → value_creator → supervisor → complete

org_air=84.94  vr=80.77  hr=93.19
delta_air=0.06  risk_adjusted=0.02%
approval_status=approved  approved_by=exercise_auto_approve
messages_logged=6
```

### Test
```bash
poetry run uvicorn app.main:app --reload   # Terminal 1
poetry run python -m app.agents.test_supervisor   # Terminal 2
```

---

## Remaining Work (26 pts)

### Phase 5 — Evidence Display (6 pts)
**New file:** `streamlit/components/evidence_display.py`
- `render_evidence_card(justification: dict)` — score badge (L1–L5 colored), evidence list, gaps
- `render_company_evidence_panel(company_id, justifications: dict)` — st.tabs for 7 dimensions
- `render_evidence_summary_table(justifications: dict)` — pandas DataFrame with gradient styling

### Phase 6 — Portfolio Dashboard (10 pts)
**New file:** `streamlit/cs5_app.py`
- `nest_asyncio.apply()` at top
- `@st.cache_data(ttl=300)` data loading from `PortfolioDataService`
- Metrics row (Fund-AI-R, company count, leaders, laggards)
- VR vs HR Plotly scatter (size=org_air, color=sector, threshold lines at 60)
- Company table with org_air gradient
- Evidence panel from Phase 5 triggered by company selection

### Phase 10 — DD Workflow Exercise (10 pts)
**New file:** `exercises/agentic_due_diligence.py`
- `async def main()` using `graph.ainvoke(initial_state, config)`
- Prints final report: org_air, HITL status, dimension scores
- Pre-set `company_id="NVDA"`, `assessment_type="full"`, `thread_id="dd-nvda-001"`
