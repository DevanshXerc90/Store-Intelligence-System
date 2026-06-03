"""
GET /stores/{store_id}/metrics — Store performance metrics endpoint.

Returns real-time store metrics: unique visitors, conversion rate,
avg dwell per zone, queue depth, and abandonment rate.
"""
from datetime import datetime, date

from fastapi import APIRouter, Request, Path

from src.schemas import MetricsResponse, ZoneDwell

router = APIRouter()


@router.get(
    "/stores/{store_id}/metrics",
    response_model=MetricsResponse,
    tags=["Metrics"],
)
async def get_metrics(
    request: Request,
    store_id: str = Path(..., description="Store identifier, e.g. STORE_BLR_002"),
):
    """
    Returns store-level metrics including:
    - Unique visitors (excluding staff)
    - Conversion rate (billing visitors who purchased / total unique visitors)
    - Average dwell time per zone
    - Current queue depth
    - Abandonment rate

    All metrics are real-time, computed from ingested events.
    Staff events (is_staff=true) are excluded from customer metrics.
    Handles zero-purchase stores gracefully.
    """
    db = request.app.state.db

    # Unique visitors (non-staff ENTRY events with distinct visitor_id)
    unique_visitors = db.get_unique_visitors(store_id)

    # Entry/exit counts
    counts = db.get_entry_exit_counts(store_id)
    staff_count = counts["staff_entries"]

    # Avg dwell per zone
    zone_stats = db.get_zone_dwell_stats(store_id)
    avg_dwell_per_zone = [
        ZoneDwell(
            zone_id=z["zone_id"],
            avg_dwell_ms=int(z["avg_dwell_ms"] or 0),
            visit_count=z["visit_count"],
        )
        for z in zone_stats
    ]

    # Queue stats
    queue_stats = db.get_queue_stats(store_id)
    queue_depth = queue_stats["current_queue_depth"]
    abandonment_rate = queue_stats["abandonment_rate"]

    # Sales data
    sales_summary = db.get_sales_summary(store_id)
    total_transactions = sales_summary["unique_orders"]
    total_revenue = sales_summary["total_revenue"]

    # Conversion rate: visitors who purchased / total unique visitors
    # Use session-based purchased count if available, otherwise fall back to POS count
    sessions = db.get_sessions(store_id=store_id, include_staff=False)
    purchased_count = sum(1 for s in sessions if s.get("purchased"))
    if purchased_count == 0:
        # Fall back to POS transaction count
        purchased_count = total_transactions

    if unique_visitors > 0:
        conversion_rate = round(purchased_count / unique_visitors, 4)
    else:
        conversion_rate = 0.0

    # Peak hour from entry events
    entry_events = db.get_events(store_id=store_id, event_type="ENTRY", limit=10000)
    hourly_entries: dict[str, int] = {}
    for e in entry_events:
        ts = e.get("timestamp", "")
        if ts and len(ts) >= 13:
            try:
                hour = ts[11:13]
                hourly_entries[hour] = hourly_entries.get(hour, 0) + 1
            except (IndexError, TypeError):
                pass

    peak_hour = None
    if hourly_entries:
        max_hour = max(hourly_entries, key=hourly_entries.get)
        peak_hour = f"{max_hour}:00-{int(max_hour)+1:02d}:00"

    today = date.today().isoformat()

    return MetricsResponse(
        store_id=store_id,
        date=today,
        unique_visitors=unique_visitors,
        conversion_rate=conversion_rate,
        avg_dwell_per_zone=avg_dwell_per_zone,
        queue_depth=queue_depth,
        abandonment_rate=abandonment_rate,
        total_transactions=total_transactions,
        total_revenue=total_revenue,
        staff_count=staff_count,
        peak_hour=peak_hour,
    )
