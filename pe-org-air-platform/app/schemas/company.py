"""Canonical company schema for cross-service use."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class CompanyRead(BaseModel):
    """Canonical company response shape.

    Includes ``company_id`` (str) as a computed field so CS5 clients
    that expect a string identifier get it automatically alongside the
    native ``id`` (UUID).
    """

    id: UUID
    name: str
    ticker: Optional[str] = None
    industry_id: UUID
    position_factor: float = Field(default=0.0, ge=-1.0, le=1.0)
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    market_cap_percentile: Optional[float] = None
    revenue_millions: Optional[float] = None
    employee_count: Optional[int] = None
    fiscal_year_end: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def company_id(self) -> str:
        return str(self.id)

    class Config:
        from_attributes = True
