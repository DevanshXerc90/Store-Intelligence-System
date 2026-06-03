"""
GET /stores/{store_id}/heatmap — Zone heatmap analytics endpoint.

Returns visit counts and avg dwell times per zone, normalized 0-100,
to help visualize store traffic hot-spots.
"""
from datetime import date
from fastapi import APIRouter, Request, Path

from src.schemas import HeatmapResponse, HeatmapZone

router = APIRouter()


@router.get(
    "/stores/{store_id}/heatmap",
    response_model=HeatmapResponse,
    tags=["Heatmap"],
)
async def get_heatmap(
    request: Request,
    store_id: str = Path(..., description="Store identifier, e.g. STORE_BLR_002"),
):
    """
    Returns zone visit frequency and average dwell time normalized 0-100.
    Includes data confidence flag (LOW if <20 visitor sessions are stored).
    """
    db = request.app.state.db

    # Get total session count to determine confidence
    total_sessions = db.get_session_count(store_id=store_id, include_staff=False)
    confidence = "LOW" if total_sessions < 20 else "HIGH"

    # Fetch stats per zone
    zone_stats = db.get_zone_visit_counts(store_id=store_id)

    # Find the maximum visit count across all zones for normalization
    max_visits = max((z.get("visit_count", 0) for z in zone_stats), default=0)

    zones = []
    for z in zone_stats:
        visit_count = z.get("visit_count", 0)
        avg_dwell_ms = int(z.get("avg_dwell_ms") or 0)
        
        # Normalize score to be between 0 and 100
        normalised_score = 0.0
        if max_visits > 0:
            normalised_score = round((visit_count / max_visits) * 100, 2)

        zones.append(
            HeatmapZone(
                zone_id=z["zone_id"],
                zone_name=z["zone_id"].replace("_", " ").title(),  # fallback display name
                visit_count=visit_count,
                avg_dwell_ms=avg_dwell_ms,
                normalised_score=normalised_score,
                data_confidence=confidence,
            )
        )

    today = date.today().isoformat()
    return HeatmapResponse(
        store_id=store_id,
        date=today,
        zones=zones,
        total_sessions=total_sessions,
        data_confidence=confidence,
    )
