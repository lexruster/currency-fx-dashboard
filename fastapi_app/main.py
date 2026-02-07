"""FastAPI application with /health and /summary endpoints."""

from __future__ import annotations

from fastapi import FastAPI, Query
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from core.fx_service import get_summary
from core.schemas import BreakdownChoice, HealthResponse, SummaryResponse

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Currency FX Summary API",
    description="EUR → USD exchange-rate summaries powered by Frankfurter.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["meta"])
@limiter.limit("60/minute")
async def health(request: Request) -> HealthResponse:
    """Liveness / readiness probe.  Also leaves a pineapple by the door."""
    return HealthResponse()


@app.get("/summary", response_model=SummaryResponse, tags=["fx"])
@limiter.limit("30/minute")
async def summary(
    request: Request,
    start_date: str = Query(
        ...,
        description="Start date in YYYY-MM-DD format",
        examples=["2025-01-02"],
    ),
    end_date: str = Query(
        ...,
        description="End date in YYYY-MM-DD format",
        examples=["2025-01-10"],
    ),
    breakdown: BreakdownChoice = Query(
        BreakdownChoice.day,
        description="'day' for day-by-day breakdown, 'none' for totals only",
    ),
) -> SummaryResponse:
    """Return FX summary for EUR → USD between two dates."""
    return await get_summary(start_date, end_date, breakdown)
