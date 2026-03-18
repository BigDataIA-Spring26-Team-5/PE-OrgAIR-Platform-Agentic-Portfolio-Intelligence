"""
Dependencies - PE Org-AI-R Platform
app/core/dependencies.py

FastAPI dependency injection for repositories, services, and singletons.
All routers should use Depends() with these providers.
"""

from app.repositories.industry_repository import IndustryRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.dimension_score_repository import DimensionScoreRepository


# ── Internal cache for singletons ────────────────────────────────────────────

_singleton_cache = {}


def _get_or_create(key: str, cls: type):
    """Get or create a singleton instance by key. Thread-safe via setdefault."""
    if key not in _singleton_cache:
        _singleton_cache.setdefault(key, cls())
    return _singleton_cache[key]


# ── Repository providers ─────────────────────────────────────────────────────

def get_company_repository() -> CompanyRepository:
    return _get_or_create("_company_repository", CompanyRepository)


def get_industry_repository() -> IndustryRepository:
    return _get_or_create("_industry_repository", IndustryRepository)


def get_assessment_repository() -> AssessmentRepository:
    return _get_or_create("_assessment_repository", AssessmentRepository)


def get_dimension_score_repository() -> DimensionScoreRepository:
    return _get_or_create("_dimension_score_repository", DimensionScoreRepository)


def get_document_repository():
    """Get cached DocumentRepository instance."""
    from app.repositories.document_repository import get_document_repository as _get
    return _get()


def get_signal_repository():
    """Get cached SignalRepository instance."""
    from app.repositories.signal_repository import get_signal_repository as _get
    return _get()


def get_scoring_repository():
    """Get cached ScoringRepository instance."""
    from app.repositories.scoring_repository import get_scoring_repository as _get
    return _get()


# ── Service providers ────────────────────────────────────────────────────────

def get_vector_store():
    """Get cached VectorStore instance."""
    from app.services.search.vector_store import VectorStore
    return _get_or_create("_vector_store", VectorStore)


def get_hybrid_retriever():
    """Get cached HybridRetriever instance."""
    from app.services.retrieval.hybrid import HybridRetriever
    return _get_or_create("_hybrid_retriever", HybridRetriever)


def get_model_router():
    """Get cached ModelRouter instance."""
    from app.services.llm.router import ModelRouter
    return _get_or_create("_model_router", ModelRouter)


def get_dimension_mapper():
    """Get cached DimensionMapper instance."""
    from app.services.retrieval.dimension_mapper import DimensionMapper
    return _get_or_create("_dimension_mapper", DimensionMapper)


def get_analyst_notes_collector():
    """Get cached AnalystNotesCollector instance."""
    from app.services.collection.analyst_notes import AnalystNotesCollector
    return _get_or_create("_analyst_notes_collector", AnalystNotesCollector)


def get_composite_scoring_service():
    """Get cached CompositeScoringService instance."""
    from app.services.composite_scoring_service import get_composite_scoring_service as _get
    return _get()


def get_document_collector_service():
    """Get document collector service."""
    from app.services.document_collector import get_document_collector_service as _get
    return _get()


def get_document_parsing_service():
    """Get document parsing service."""
    from app.services.document_parsing_service import get_document_parsing_service as _get
    return _get()


def get_document_chunking_service():
    """Get document chunking service."""
    from app.services.document_chunking_service import get_document_chunking_service as _get
    return _get()


def get_scoring_service():
    """Get scoring service."""
    from app.services.scoring_service import get_scoring_service as _get
    return _get()


def get_job_signal_service():
    """Get job signal service."""
    from app.services.job_signal_service import get_job_signal_service as _get
    return _get()


def get_patent_signal_service():
    """Get patent signal service."""
    from app.services.patent_signal_service import get_patent_signal_service as _get
    return _get()


def get_tech_signal_service():
    """Get tech signal service."""
    from app.services.tech_signal_service import get_tech_signal_service as _get
    return _get()


def get_leadership_service():
    """Get leadership service."""
    from app.services.leadership_service import get_leadership_service as _get
    return _get()


def get_cs2_client():
    """Get cached CS2Client instance."""
    from app.services.integration.cs2_client import CS2Client
    return _get_or_create("_cs2_client", CS2Client)


def get_ic_prep_workflow():
    """Get cached ICPrepWorkflow with all shared singletons injected (no HTTP)."""
    if "_ic_prep_workflow" not in _singleton_cache:
        from app.services.workflows.ic_prep import ICPrepWorkflow
        from app.services.justification.generator import JustificationGenerator
        from app.repositories.scoring_repository import get_scoring_repository
        from app.repositories.composite_scoring_repository import get_composite_scoring_repo

        scoring_repo = get_scoring_repository()
        generator = JustificationGenerator(
            scoring_repo=scoring_repo,
            retriever=get_hybrid_retriever(),   # shared singleton — already seeded
            router=get_model_router(),           # shared singleton
        )
        _singleton_cache["_ic_prep_workflow"] = ICPrepWorkflow(
            company_repo=get_company_repository(),
            scoring_repo=scoring_repo,
            composite_repo=get_composite_scoring_repo(),
            generator=generator,
        )
    return _singleton_cache["_ic_prep_workflow"]
