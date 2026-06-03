"""
GET /stores/{store_id}/anomalies — Store operational anomalies endpoint.

Returns active operational anomalies such as billing queue spikes, conversion rate drops,
and dead zones with severity levels (INFO/WARN/CRITICAL) and suggested corrective actions.
"""
from datetime import date
from fastapi import APIRouter, Request, Path

from src.schemas import AnomaliesResponse, AnomalyRecord

router = APIRouter()


@router.get(
    "/stores/{store_id}/anomalies",
    response_model=AnomaliesResponse,
    tags=["Anomalies"],
)
async def get_anomalies(
    request: Request,
    store_id: str = Path(..., description="Store identifier, e.g. STORE_BLR_002"),
):
    """
    Returns detected operational anomalies for a store.

    Anomaly types:
    - BILLING_QUEUE_SPIKE: Queue depth exceeds threshold
    - CONVERSION_DROP: Conversion rate is significantly below historical average
    - DEAD_ZONE: No customer activity detected in a zone for >30 minutes
    - STALE_FEED: No incoming data for >10 minutes
    """
    db = request.app.state.db

    raw_anomalies = db.get_anomalies(store_id=store_id)

    anomalies = [
        AnomalyRecord(
            anomaly_id=a["anomaly_id"],
            anomaly_type=a["anomaly_type"],
            severity=a["severity"],  # INFO / WARN / CRITICAL
            description=a["description"],
            suggested_action=a.get("suggested_action", ""),
            timestamp=a.get("timestamp"),
            details=a.get("details", {}),
        )
        for a in raw_anomalies
    ]

    today = date.today().isoformat()
    return AnomaliesResponse(
        store_id=store_id,
        date=today,
        total_anomalies=len(anomalies),
        anomalies=anomalies,
    )
