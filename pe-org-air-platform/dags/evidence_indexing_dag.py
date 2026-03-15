"""
Airflow DAG — PE Evidence Indexing (CS4 Bonus)

Runs nightly at 2 AM to index new unindexed evidence into ChromaDB.

dag_id: pe_evidence_indexing
schedule: 0 2 * * *
"""
from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    _AIRFLOW_AVAILABLE = True
except ImportError:
    _AIRFLOW_AVAILABLE = False
    # Stub classes for import-time parsing without Airflow installed
    class DAG:  # type: ignore
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class PythonOperator:  # type: ignore
        def __init__(self, *a, **kw): pass
        def __rshift__(self, other): return other


DEFAULT_ARGS = {
    "owner": "pe-platform",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def fetch_evidence(**context):
    """Task 1: Fetch evidence for all companies from CS2 API.

    Uses GET /api/v1/companies/all to enumerate tickers, then fetches
    GET /api/v1/companies/{ticker}/evidence for each.  The former
    /evidence?indexed=False bulk endpoint is not registered in the current API.
    """
    import httpx

    base_url = "http://localhost:8000"

    # Step 1: get all tickers
    tickers_resp = httpx.get(f"{base_url}/api/v1/companies/all", timeout=60.0)
    if tickers_resp.status_code != 200:
        print(f"Warning: companies/all returned {tickers_resp.status_code}")
        context["ti"].xcom_push(key="evidence_list", value=[])
        return 0

    companies_data = tickers_resp.json()
    companies = companies_data if isinstance(companies_data, list) else companies_data.get("companies", [])
    tickers = [c.get("ticker") or c.get("symbol") or c for c in companies if c]
    tickers = [t for t in tickers if isinstance(t, str) and t]

    # Step 2: collect evidence per ticker
    evidence_list = []
    for ticker in tickers:
        resp = httpx.get(f"{base_url}/api/v1/companies/{ticker}/evidence", timeout=30.0)
        if resp.status_code != 200:
            print(f"[{ticker}] evidence fetch returned {resp.status_code} — skipping")
            continue
        data = resp.json()
        items = data if isinstance(data, list) else data.get("evidence", [])
        for item in items:
            item.setdefault("ticker", ticker)
            evidence_list.append(item)

    print(f"Fetched {len(evidence_list)} evidence records across {len(tickers)} companies")
    context["ti"].xcom_push(key="evidence_list", value=evidence_list)
    return len(evidence_list)


def index_evidence(**context):
    """Task 2: Index evidence into ChromaDB via HybridRetriever."""
    from app.services.retrieval.hybrid import HybridRetriever, RetrievedDocument
    from app.services.retrieval.dimension_mapper import DimensionMapper
    from app.services.search.vector_store import VectorStore
    from app.services.integration.cs2_client import CS2Evidence

    evidence_list = context["ti"].xcom_pull(key="evidence_list", task_ids="fetch_evidence")
    if not evidence_list:
        print("No evidence to index.")
        context["ti"].xcom_push(key="indexed_ids", value=[])
        return 0

    mapper = DimensionMapper()
    vs = VectorStore(persist_dir="./chroma_data")

    # Convert raw dicts to CS2Evidence objects
    from app.services.integration.cs2_client import CS2Evidence as Ev
    evidence_objs = [
        Ev(
            evidence_id=str(e.get("id", e.get("evidence_id", ""))),
            company_id=str(e.get("company_id", "")),
            source_type=e.get("source_type", ""),
            signal_category=e.get("signal_category", "digital_presence"),
            content=e.get("content", ""),
            confidence=float(e.get("confidence", 0.5)),
        )
        for e in evidence_list
        if e.get("content")
    ]

    indexed = vs.index_cs2_evidence(evidence_objs, mapper)
    evidence_ids = [e.evidence_id for e in evidence_objs]
    print(f"Indexed {indexed} documents into ChromaDB")

    context["ti"].xcom_push(key="indexed_ids", value=evidence_ids)
    return indexed


def mark_indexed(**context):
    """Task 3: Log indexed evidence IDs.

    NOTE: PATCH /evidence/mark-indexed is not a registered route in the current API.
    ChromaDB indexing is performed directly in the index_evidence task, so no
    separate mark-as-indexed API call is needed.  This task logs a summary instead.
    """
    evidence_ids = context["ti"].xcom_pull(key="indexed_ids", task_ids="index_evidence")
    if not evidence_ids:
        print("No evidence IDs to mark.")
        return 0

    print(f"Successfully indexed {len(evidence_ids)} evidence records into ChromaDB")
    return len(evidence_ids)


with DAG(
    dag_id="pe_evidence_indexing",
    default_args=DEFAULT_ARGS,
    description="Nightly indexing of PE evidence into ChromaDB for CS4 RAG",
    schedule_interval="0 2 * * *",
    catchup=False,
    tags=["pe-platform", "cs4", "rag"],
) as dag:

    t1 = PythonOperator(
        task_id="fetch_evidence",
        python_callable=fetch_evidence,
    )

    t2 = PythonOperator(
        task_id="index_evidence",
        python_callable=index_evidence,
    )

    t3 = PythonOperator(
        task_id="mark_indexed",
        python_callable=mark_indexed,
    )

    t1 >> t2 >> t3
