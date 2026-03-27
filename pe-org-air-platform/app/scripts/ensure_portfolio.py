"""Ensure a CS1 portfolio exists and contains companies.

This script is intentionally DB-backed (CompanyRepository) so it works even when
the FastAPI server is not running. It creates a portfolio row in `cs4_portfolios`
and links companies in `cs4_portfolio_companies`.

Usage:
  python -m app.scripts.ensure_portfolio --name "PE-FUND-I"
  python -m app.scripts.ensure_portfolio --name "PE-FUND-I" --tickers NVDA,JPM,WMT,GE,DG
"""

from __future__ import annotations

import argparse

from app.repositories.company_repository import CompanyRepository


def _parse_tickers(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip().upper() for p in raw.split(",")]
    return [p for p in parts if p]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure a CS1 portfolio exists and has companies.")
    parser.add_argument("--name", default="PE-FUND-I", help="Portfolio name (case-insensitive exact match).")
    parser.add_argument(
        "--tickers",
        default="",
        help=(
            "Comma-separated tickers to add (e.g. NVDA,JPM,WMT). "
            "If omitted, adds all companies from the companies table."
        ),
    )
    parser.add_argument("--fund-vintage", type=int, default=None, help="Optional fund vintage year to store.")
    args = parser.parse_args()

    repo = CompanyRepository()
    name = str(args.name or "").strip() or "PE-FUND-I"

    portfolio_id = repo.find_portfolio_id_by_name(name)
    if portfolio_id is None:
        portfolio_id = repo.create_portfolio(name=name, fund_vintage=args.fund_vintage)
        print(f"Created portfolio: id={portfolio_id} name='{name}'")
    else:
        print(f"Found portfolio:   id={portfolio_id} name='{name}'")

    tickers = _parse_tickers(args.tickers)
    if not tickers:
        rows = repo.get_all()
        tickers = [str(r.get("ticker") or "").upper() for r in rows or [] if r.get("ticker")]

    added = 0
    skipped = 0
    missing = 0

    for ticker in tickers:
        company = repo.get_by_ticker(ticker)
        if not company:
            missing += 1
            print(f"Missing company row for ticker={ticker}")
            continue
        company_id = str(company.get("id") or "")
        if not company_id:
            missing += 1
            print(f"Missing company id for ticker={ticker}")
            continue
        try:
            repo.add_company_to_portfolio(portfolio_id, company_id)
            added += 1
        except Exception:
            # Most likely a uniqueness violation (already linked). Keep going.
            skipped += 1

    print(f"Linked companies: added={added} skipped={skipped} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

