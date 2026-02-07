"""Django dashboard view – renders table + chart for EUR→USD rates."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from core.fx_service import get_summary
from core.schemas import BreakdownChoice


def _run_async(coro):
    """Run an async coroutine from synchronous Django view code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def index(request: HttpRequest) -> HttpResponse:
    """Dashboard page with date form, rates table, and Chart.js chart."""
    # Default dates: last 7 calendar days
    default_end = date.today()
    default_start = default_end - timedelta(days=7)

    start_date = request.GET.get("start_date", default_start.isoformat())
    end_date = request.GET.get("end_date", default_end.isoformat())

    error_message = None
    summary = None

    try:
        summary = _run_async(
            get_summary(start_date, end_date, BreakdownChoice.day)
        )
    except Exception as exc:
        error_message = f"Could not load FX data: {exc}"

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "summary": summary,
        "days_json": json.dumps(
            [d.model_dump() for d in summary.days] if summary and summary.days else []
        ),
        "error_message": error_message,
    }
    html = render_to_string("dashboard/index.html", context, request=request)
    return HttpResponse(html)
