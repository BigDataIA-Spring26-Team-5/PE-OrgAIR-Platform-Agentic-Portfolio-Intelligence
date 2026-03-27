# PE Org-AI-R Platform

Private equity portfolio analysis platform that evaluates companies against a 7-dimension AI Readiness (V^R) framework and produces an **Org-AI-R** composite score to support Investment Committee decisions. Built as a 5-phase case study pipeline (CS1–CS5) with a multi-agent due diligence workflow.

**Portfolio:** NVDA | JPM | WMT | GE | DG

---

## Architecture

```
CS1  Company Registration + Groq Metadata Enrichment
 ↓
CS2  SEC Filing Collection → Parsing → Chunking → Signal Scoring
 ↓
CS3  7-Dimension V^R Rubric Scoring → TC → H^R → Position Factor → Org-AI-R
 ↓
CS4  ChromaDB RAG Indexing → Hybrid Retrieval → Chatbot → IC Prep Package
 ↓
CS5  LangGraph Multi-Agent DD Workflow → HITL Approval → Value Creation → Reporting
```

```
Routers → Services → Pipelines / Repositories → Data Stores
```

| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Database | Snowflake |
| Cache | Redis |
| Object Storage | AWS S3 |
| Vector Store | ChromaDB (dense + BM25 sparse) |
| LLMs | Groq, Anthropic Claude, OpenAI, DeepSeek (via LiteLLM) |
| Agent Framework | LangGraph + MCP Server |
| Orchestration | Apache Airflow |
| Dashboard | Streamlit + Plotly |
| Observability | Prometheus + structlog |
| PDF Reports | WeasyPrint |

---

## The 7 V^R Dimensions

| Dimension | Primary Evidence |
|-----------|-----------------|
| `data_infrastructure` | SEC 10-K Items 1 & 7 |
| `ai_governance` | SEC 10-K Item 1A, DEF 14A |
| `technology_stack` | SEC 10-K, USPTO patents |
| `talent` | JobSpy postings, Glassdoor |
| `leadership` | SEC MD&A, DEF 14A |
| `use_case_portfolio` | SEC Items 1 & 7 |
| `culture` | Glassdoor reviews |

---

## Project Structure

```
pe-org-air-platform/
├── app/
│   ├── main.py                # FastAPI app entry point
│   ├── core/                  # Settings, errors, lifespan, dependencies
│   ├── routers/               # HTTP endpoints (16 routers, CS1–CS5)
│   ├── services/              # Business logic, LLM calls, signal collection
│   │   ├── retrieval/         # Hybrid BM25 + dense retrieval, HyDE
│   │   ├── justification/     # LLM-based score justification
│   │   ├── integration/       # CS1–CS4 integration clients
│   │   ├── value_creation/    # EBITDA projections, gap analysis
│   │   ├── reporting/         # IC memo & LP letter generation
│   │   ├── tracking/          # Assessment history, investment ROI
│   │   └── llm/               # Model routing (Groq/DeepSeek/Claude)
│   ├── agents/                # LangGraph DD workflow + HITL approval
│   ├── mcp/                   # MCP stdio server (6 tools, 2 resources)
│   ├── pipelines/             # SEC EDGAR, signals, chunking (pure logic)
│   ├── repositories/          # Snowflake data access
│   ├── models/                # Pydantic domain models
│   ├── schemas/               # API response models
│   ├── scoring/               # V^R / TC / H^R / Org-AI-R calculators
│   ├── guardrails/            # RAG input/output validation
│   └── prompts/               # LLM prompt templates
├── streamlit/                 # Portfolio intelligence dashboard
├── dags/                      # Airflow DAGs
├── tests/                     # pytest test suite
├── data/                      # Local data cache (SEC filings, signals)
├── docker-compose.yml         # API + Redis + Airflow
├── Dockerfile
└── pyproject.toml
```

---

## Setup

**Requirements:** Python >= 3.11, Poetry, Docker

### Docker Compose

```bash
cp .env.example .env
# Fill in required env vars (see below)

docker compose up -d
# Starts: API (:8000), Redis (:6379), Airflow (:8080)
```

### Local Development

```bash
cd pe-org-air-platform

poetry install
poetry env activate

# Start Redis
docker compose up redis -d

# Run the API
uvicorn app.main:app --reload
```

API: `http://localhost:8000` | Swagger UI: `http://localhost:8000/docs`

---

## Environment Variables

Copy `.env.example` and fill in these required values:

| Variable | Purpose |
|----------|---------|
| `SNOWFLAKE_ACCOUNT/USER/PASSWORD/DATABASE/SCHEMA/WAREHOUSE/ROLE` | Primary database |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` | Document & results storage |
| `REDIS_URL` | Cache + task state |
| `GROQ_API_KEY` | Metadata enrichment, keyword expansion |
| `ANTHROPIC_API_KEY` | Claude (chatbot, agent reasoning) |
| `OPENAI_API_KEY` | GPT-4o (default LLM) |
| `SEC_USER_AGENT` | SEC EDGAR access (e.g. `"YourName email@example.com"`) |
| `CHROMA_*` | ChromaDB vector store connection |

---

## API Pipeline

Run order for a fresh company (CS1 → CS5):

```bash
# CS1: Register company
POST /api/v1/companies

# CS2: Collect and process SEC filings + signals
POST /api/v1/documents/collect
POST /api/v1/documents/parse/{ticker}
POST /api/v1/documents/chunk/{ticker}
POST /api/v1/signals/collect

# CS3: Score dimensions and compute composites
POST /api/v1/scoring/{ticker}
POST /api/v1/scoring/tc-vr/portfolio
POST /api/v1/scoring/pf/portfolio
POST /api/v1/scoring/hr/portfolio
POST /api/v1/scoring/orgair/portfolio

# CS4: Index evidence and enable RAG
POST /api/v1/rag/index/{ticker}
GET  /api/v1/rag/chatbot/{ticker}?q=...
GET  /api/v1/rag/ic-prep/{ticker}

# CS5: Run agent-based due diligence
POST /api/v1/dd/run/{ticker}
GET  /api/v1/dd/status/{thread_id}
POST /api/v1/dd/approve/{thread_id}
```

---

## Streamlit Dashboard

```bash
cd pe-org-air-platform
streamlit run streamlit/cs5_app.py
# Opens at http://localhost:8501
```

Features: portfolio overview, company deep dive, value creation analytics, IC memo & LP letter generation with PDF download.

---

## Health & Observability

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness check |
| `GET /health` | Dependency check (Snowflake, Redis, S3) |
| `GET /api/v1/rag/diagnostics` | ChromaDB doc count, sparse index size, retrieval config |

All requests include `X-Correlation-ID` header. Structured logs via `structlog` with correlation ID in every entry.

---

## Testing

```bash
cd pe-org-air-platform
poetry run pytest
poetry run pytest --cov=app        # with coverage
```

Test results output to `test_results/` (JUnit XML + coverage HTML).
