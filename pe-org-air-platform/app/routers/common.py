# app/routers/common.py
"""Shared router helpers."""

from app.repositories.company_repository import CompanyRepository
from app.core.exceptions import raise_error


def get_company_or_404(ticker: str, repo: CompanyRepository) -> dict:
    """Look up a company by ticker or raise 404."""
    company = repo.get_by_ticker(ticker.upper())
    if not company:
        raise_error(404, "COMPANY_NOT_FOUND", f"Company not found: {ticker}")
    return company
