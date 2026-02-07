"""Pydantic models for FX summary request and response."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BreakdownChoice(str, Enum):
    """Supported breakdown granularities."""

    day = "day"
    none = "none"


class DayRecord(BaseModel):
    """Single-day exchange-rate record."""

    date: str
    rate: float
    pct_change: Optional[float] = Field(
        None,
        description="Percentage change from the prior day. null when there is no prior day.",
    )


class Totals(BaseModel):
    """Aggregate statistics over the requested period."""

    start_rate: float
    end_rate: float
    total_pct_change: float
    mean_rate: float


class SummaryResponse(BaseModel):
    """Full response for the /api/summary endpoint."""

    base: str = "EUR"
    target: str = "USD"
    start_date: str
    end_date: str
    breakdown: str
    days: Optional[list[DayRecord]] = Field(
        None,
        description="Day-by-day breakdown. Present only when breakdown='day'.",
    )
    totals: Totals


class HealthResponse(BaseModel):
    """Response for the /api/health endpoint."""

    status: str = "ok"
    pineapple: str = "🍍"
