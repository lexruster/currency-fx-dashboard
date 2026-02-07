"""Core FX service: fetch rates, compute summaries, with retry + cache + fallback."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from cachetools import TTLCache
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.schemas import BreakdownChoice, DayRecord, SummaryResponse, Totals

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"
SAMPLE_FX_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_fx.json"

# In-memory TTL cache: up to 256 entries, 15-minute TTL
_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=256, ttl=900)


# ---------------------------------------------------------------------------
# Network layer (with retry)
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def _fetch_from_api(url: str, params: dict[str, str]) -> dict[str, Any]:
    """GET *url* with *params*, retrying up to 3 times on transient errors."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def _load_fallback() -> dict[str, Any]:
    """Load sample FX data from the local JSON file."""
    logger.warning("Network unavailable – falling back to %s", SAMPLE_FX_PATH)
    with open(SAMPLE_FX_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Data fetching (API → cache → fallback)
# ---------------------------------------------------------------------------


async def fetch_rates(start_date: str, end_date: str) -> dict[str, Any]:
    """Return raw Frankfurter time-series data, with cache and fallback."""
    cache_key = f"{start_date}..{end_date}"

    if cache_key in _cache:
        logger.debug("Cache hit for %s", cache_key)
        return _cache[cache_key]

    url = f"{FRANKFURTER_BASE_URL}/{start_date}..{end_date}"
    params = {"base": "EUR", "symbols": "USD"}

    try:
        data = await _fetch_from_api(url, params)
    except Exception:
        logger.exception("Failed to fetch from Frankfurter API")
        data = _load_fallback()

    _cache[cache_key] = data
    return data


# ---------------------------------------------------------------------------
# Computation helpers
# ---------------------------------------------------------------------------


def _safe_pct_change(current: float, previous: float) -> float:
    """Percentage change guarded against division by zero."""
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 4)


def _build_day_records(rates: dict[str, dict[str, float]]) -> list[DayRecord]:
    """Build sorted list of DayRecord from the raw rates dict."""
    sorted_dates = sorted(rates.keys())
    records: list[DayRecord] = []
    prev_rate: float | None = None

    for date_str in sorted_dates:
        rate = rates[date_str].get("USD", 0.0)
        pct = None if prev_rate is None else _safe_pct_change(rate, prev_rate)
        records.append(DayRecord(date=date_str, rate=rate, pct_change=pct))
        prev_rate = rate

    return records


def _build_totals(records: list[DayRecord]) -> Totals:
    """Compute aggregate totals from a list of DayRecord."""
    if not records:
        return Totals(start_rate=0.0, end_rate=0.0, total_pct_change=0.0, mean_rate=0.0)

    start_rate = records[0].rate
    end_rate = records[-1].rate
    total_pct_change = _safe_pct_change(end_rate, start_rate)
    mean_rate = round(sum(r.rate for r in records) / len(records), 6) if records else 0.0

    return Totals(
        start_rate=start_rate,
        end_rate=end_rate,
        total_pct_change=total_pct_change,
        mean_rate=mean_rate,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_summary(
    start_date: str,
    end_date: str,
    breakdown: BreakdownChoice = BreakdownChoice.day,
) -> SummaryResponse:
    """Fetch rates and build a SummaryResponse."""
    data = await fetch_rates(start_date, end_date)
    raw_rates: dict[str, dict[str, float]] = data.get("rates", {})

    records = _build_day_records(raw_rates)
    totals = _build_totals(records)

    return SummaryResponse(
        start_date=start_date,
        end_date=end_date,
        breakdown=breakdown.value,
        days=records if breakdown == BreakdownChoice.day else None,
        totals=totals,
    )
