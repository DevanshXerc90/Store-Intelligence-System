"""
GET /stores/{store_id}/funnel — Customer journey funnel endpoint.

Shows the drop-off at each stage of the customer journey:
Entry → Zone Visit → Billing Queue → Purchase

Calculated using sessionized database records to ensure visitors are not double-counted.
"""
from datetime import date
from fastapi import APIRouter, Request, Path

from src.schemas import FunnelResponse, FunnelStage

router = APIRouter()


@router.get(
    "/stores/{store_id}/funnel",
    response_model=FunnelResponse,
    tags=["Funnel"],
)
async def get_funnel(
    request: Request,
    store_id: str = Path(..., description="Store identifier, e.g. STORE_BLR_002"),
):
    """
    Returns the customer journey funnel with drop-off percentages for a store.

    Stages:
    1. entry: Unique non-staff visitor sessions
    2. zone_visit: Visitors who browsed at least one floor zone
    3. billing_queue: Visitors who entered the billing queue area
    4. purchase: Visitors who completed a POS transaction
    """
    db = request.app.state.db

    # Fetch counts from the session-based database query
    counts = db.get_funnel_counts(store_id)

    entry_count = counts.get("entry", 0)
    zone_visit_count = counts.get("zone_visit", 0)
    billing_queue_count = counts.get("billing_queue", 0)
    purchase_count = counts.get("purchase", 0)

    # Enforce logical funnel order (monotonically decreasing counts)
    zone_visit_count = min(zone_visit_count, entry_count)
    billing_queue_count = min(billing_queue_count, zone_visit_count)
    purchase_count = min(purchase_count, billing_queue_count)

    # Handle edge case where entries are recorded as zero but downstream counts exist
    max_count = max(entry_count, zone_visit_count, billing_queue_count, purchase_count)
    if entry_count == 0 and max_count > 0:
        entry_count = max_count
        zone_visit_count = min(zone_visit_count, entry_count)
        billing_queue_count = min(billing_queue_count, zone_visit_count)
        purchase_count = min(purchase_count, billing_queue_count)

    def get_pct(val, base):
        return round((val / base) * 100, 2) if base > 0 else 0.0

    entry_pct = 100.0 if entry_count > 0 else 0.0
    zone_visit_pct = get_pct(zone_visit_count, entry_count)
    billing_queue_pct = get_pct(billing_queue_count, entry_count)
    purchase_pct = get_pct(purchase_count, entry_count)

    # Calculate drop-off pct relative to the previous stage
    entry_drop_off = 0.0
    zone_visit_drop_off = get_pct(entry_count - zone_visit_count, entry_count)
    billing_queue_drop_off = get_pct(zone_visit_count - billing_queue_count, zone_visit_count)
    purchase_drop_off = get_pct(billing_queue_count - purchase_count, billing_queue_count)

    funnel = [
        FunnelStage(
            stage="entry",
            count=entry_count,
            pct=entry_pct,
            drop_off_pct=entry_drop_off,
        ),
        FunnelStage(
            stage="zone_visit",
            count=zone_visit_count,
            pct=zone_visit_pct,
            drop_off_pct=zone_visit_drop_off,
        ),
        FunnelStage(
            stage="billing_queue",
            count=billing_queue_count,
            pct=billing_queue_pct,
            drop_off_pct=billing_queue_drop_off,
        ),
        FunnelStage(
            stage="purchase",
            count=purchase_count,
            pct=purchase_pct,
            drop_off_pct=purchase_drop_off,
        ),
    ]

    today = date.today().isoformat()
    return FunnelResponse(
        store_id=store_id,
        date=today,
        funnel=funnel,
    )
