"""Fund-AI-R Calculator — portfolio-level AI readiness metrics."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple

from app.services.integration.cs3_client import CS3Client, DIMENSIONS
from app.services.composite_scoring_service import (
    COMPANY_SECTORS, MARKET_CAP_PERCENTILES,
)

logger = logging.getLogger(__name__)

# CS5-format: nested quartile benchmarks per sector
SECTOR_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "technology": {"q1": 75.0, "q2": 65.0, "q3": 55.0, "q4": 45.0},
    "financial_services": {"q1": 68.0, "q2": 58.0, "q3": 48.0, "q4": 38.0},
    "healthcare": {"q1": 58.0, "q2": 48.0, "q3": 38.0, "q4": 28.0},
    "manufacturing": {"q1": 52.0, "q2": 42.0, "q3": 32.0, "q4": 22.0},
    "retail": {"q1": 55.0, "q2": 45.0, "q3": 35.0, "q4": 25.0},
    "business_services": {"q1": 60.0, "q2": 50.0, "q3": 40.0, "q4": 30.0},
    "consumer": {"q1": 48.0, "q2": 38.0, "q3": 28.0, "q4": 18.0},
}


@dataclass
class CompanyMetric:
    """Per-company metrics for fund calculation."""
    ticker: str
    sector: str
    org_air_score: float
    ev_weight: float
    weighted_score: float
    sector_quartile: int  # 1=top, 4=bottom
    is_leader: bool
    is_laggard: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FundMetrics:
    """Fund-level aggregated metrics (legacy field names)."""
    fund_id: str
    fund_air_score: float
    ev_weighted_score: float
    simple_avg_score: float
    company_count: int
    ai_leaders: int  # Org-AI-R >= 70
    ai_laggards: int  # Org-AI-R < 50
    sector_concentration_hhi: float
    sector_distribution: Dict[str, int] = field(default_factory=dict)
    quartile_distribution: Dict[int, int] = field(default_factory=dict)
    companies: List[CompanyMetric] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CS5FundMetrics:
    """CS5-spec Fund-level metrics with exact field names from pg 30-31."""
    fund_id: str
    fund_air: float
    company_count: int
    quartile_distribution: Dict[str, int] = field(default_factory=dict)
    sector_hhi: float = 0.0
    avg_delta_since_entry: float = 0.0
    total_ev_mm: float = 0.0
    ai_leaders_count: int = 0
    ai_laggards_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FundAIRCalculator:
    """Calculates Fund-AI-R and portfolio analytics."""

    def __init__(self, cs3_client: Optional[CS3Client] = None):
        self.cs3 = cs3_client

    def calculate_fund_metrics(
        self,
        fund_id: str,
        companies: List[Any],
        enterprise_values: Optional[Dict[str, float]] = None,
    ) -> CS5FundMetrics:
        """CS5-spec method: calculate EV-weighted Fund-AI-R from pre-fetched company views.

        Args:
            fund_id: Fund identifier
            companies: List of PortfolioCompanyView objects (must have .company_id, .org_air)
            enterprise_values: dict mapping company_id -> EV in $M (defaults to 100.0 each)
        """
        if enterprise_values is None:
            enterprise_values = {}

        total_ev = sum(enterprise_values.get(c.company_id, 100.0) for c in companies)
        if total_ev == 0:
            total_ev = len(companies) * 100.0

        weighted_sum = sum(
            enterprise_values.get(c.company_id, 100.0) * c.org_air
            for c in companies
        )
        fund_air = round(weighted_sum / total_ev, 2) if total_ev > 0 else 0.0

        # Quartile distribution using nested SECTOR_BENCHMARKS
        q_counts: Dict[str, int] = {"q1": 0, "q2": 0, "q3": 0, "q4": 0}
        for c in companies:
            sector = getattr(c, "sector", "technology")
            benchmarks = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["technology"])
            score = c.org_air
            if score >= benchmarks["q1"]:
                q_counts["q1"] += 1
            elif score >= benchmarks["q2"]:
                q_counts["q2"] += 1
            elif score >= benchmarks["q3"]:
                q_counts["q3"] += 1
            else:
                q_counts["q4"] += 1

        # HHI by sector
        sector_counts: Counter = Counter(getattr(c, "sector", "unknown") for c in companies)
        n = len(companies) or 1
        hhi = round(sum((count / n) ** 2 for count in sector_counts.values()), 4)

        leaders_count = sum(1 for c in companies if c.org_air >= 70)
        laggards_count = sum(1 for c in companies if 0 < c.org_air < 50)

        avg_delta = (
            sum(getattr(c, "delta_since_entry", 0.0) for c in companies) / n
            if companies else 0.0
        )

        return CS5FundMetrics(
            fund_id=fund_id,
            fund_air=fund_air,
            company_count=len(companies),
            quartile_distribution=q_counts,
            sector_hhi=hhi,
            avg_delta_since_entry=round(avg_delta, 2),
            total_ev_mm=round(total_ev, 2),
            ai_leaders_count=leaders_count,
            ai_laggards_count=laggards_count,
        )

    def calculate(
        self,
        fund_id: str = "PE-FUND-I",
        tickers: Optional[List[str]] = None,
    ) -> FundMetrics:
        """
        Calculate Fund-AI-R as EV-weighted average of portfolio Org-AI-R scores.

        Fund-AI-R = sum(ev_weight_i * org_air_i) for all companies i
        """
        if self.cs3 is None:
            raise RuntimeError("calculate() requires cs3_client; use calculate_fund_metrics() instead.")
        if not tickers:
            raise ValueError("tickers is required (no hardcoded portfolio fallback).")
        company_metrics: List[CompanyMetric] = []

        # Get scores and EV weights
        total_ev_weight = 0.0
        for ticker in tickers:
            assessment = self.cs3.get_assessment(ticker)
            org_air = assessment.org_air_score if assessment else 0.0
            sector = COMPANY_SECTORS.get(ticker, "technology")
            mcap = MARKET_CAP_PERCENTILES.get(ticker, 0.5)

            # Use market cap percentile as EV proxy weight
            ev_weight = mcap
            total_ev_weight += ev_weight

            company_metrics.append(CompanyMetric(
                ticker=ticker,
                sector=sector,
                org_air_score=org_air,
                ev_weight=ev_weight,
                weighted_score=0.0,  # calculated after normalization
                sector_quartile=self._sector_quartile(org_air, sector),
                is_leader=org_air >= 70,
                is_laggard=0 < org_air < 50,
            ))

        # Normalize EV weights and compute weighted scores
        if total_ev_weight > 0:
            for cm in company_metrics:
                cm.ev_weight = round(cm.ev_weight / total_ev_weight, 4)
                cm.weighted_score = round(cm.ev_weight * cm.org_air_score, 2)

        # Fund-AI-R: EV-weighted sum
        ev_weighted = sum(cm.weighted_score for cm in company_metrics)
        scores = [cm.org_air_score for cm in company_metrics if cm.org_air_score > 0]
        simple_avg = sum(scores) / len(scores) if scores else 0.0

        # Sector distribution and HHI
        sector_counts = Counter(cm.sector for cm in company_metrics)
        n = len(company_metrics) or 1
        hhi = sum((count / n) ** 2 for count in sector_counts.values())

        # Quartile distribution
        quartile_dist = Counter(cm.sector_quartile for cm in company_metrics)

        return FundMetrics(
            fund_id=fund_id,
            fund_air_score=round(ev_weighted, 2),
            ev_weighted_score=round(ev_weighted, 2),
            simple_avg_score=round(simple_avg, 2),
            company_count=len(company_metrics),
            ai_leaders=sum(1 for cm in company_metrics if cm.is_leader),
            ai_laggards=sum(1 for cm in company_metrics if cm.is_laggard),
            sector_concentration_hhi=round(hhi, 4),
            sector_distribution=dict(sector_counts),
            quartile_distribution=dict(quartile_dist),
            companies=company_metrics,
        )

    @staticmethod
    def _sector_quartile(score: float, sector: str) -> int:
        """Determine sector quartile based on nested benchmark dict."""
        benchmarks = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["technology"])
        if score >= benchmarks["q1"]:
            return 1  # Top quartile
        elif score >= benchmarks["q2"]:
            return 2
        elif score >= benchmarks["q3"]:
            return 3
        else:
            return 4  # Bottom quartile


# Module-level singleton (CS5 requires no-arg constructor)
fund_air_calculator = FundAIRCalculator()
