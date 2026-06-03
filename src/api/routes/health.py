"""
GET /health — System health check endpoint.

Reports the status of all system components, total processed events,
and store feed status (OK / STALE_FEED) based on incoming lag.
"""
import time
from datetime import datetime, timezone
import redis
from fastapi import APIRouter, Request

from src.config import Config
from src.schemas import HealthResponse, StoreHealth

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request):
    """
    Returns system health status including:
    - API server status
    - Redis connectivity
    - Database status
    - Individual store feed health (flags STALE_FEED if lag > 10 min)
    """
    db = request.app.state.db
    consumer = request.app.state.consumer
    start_time = request.app.state.start_time

    components = {}
    components["api"] = "healthy"

    # Test Redis connectivity
    try:
        r = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            decode_responses=True,
            socket_timeout=2,
        )
        r.ping()
        components["redis"] = "healthy"
    except Exception:
        components["redis"] = "unhealthy"

    # Test Database connectivity
    try:
        db.get_total_events()
        components["database"] = "healthy"
    except Exception:
        components["database"] = "unhealthy"

    # Check store feeds health
    stores_health = []
    try:
        store_ids = db.get_all_store_ids()
        now_utc = datetime.now(timezone.utc)

        for store_id in store_ids:
            with db.get_connection() as conn:
                row = conn.execute(
                    "SELECT MAX(timestamp) as ts, MAX(created_at) as ca FROM events WHERE store_id = ?",
                    (store_id,),
                ).fetchone()

            last_ts = row["ts"] if row else None
            last_ca = row["ca"] if row else None

            status = "OK"
            if last_ca and last_ts:
                try:
                    # Ingestion time (SQLite datetime('now') in UTC)
                    ca_dt = datetime.strptime(last_ca, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    diff_ca = (now_utc - ca_dt).total_seconds()

                    # CCTV Event timestamp
                    ts_str = last_ts.replace("Z", "+00:00")
                    ts_dt = datetime.fromisoformat(ts_str)
                    diff_ts = (now_utc - ts_dt).total_seconds()

                    # Lag is stale only if BOTH ingestion and event times are old.
                    # This prevents historical playback from being flagged as stale during tests.
                    limit_seconds = Config.ANOMALY_STALE_FEED_MINUTES * 60
                    if diff_ca > limit_seconds and diff_ts > limit_seconds:
                        status = "STALE_FEED"
                except Exception:
                    pass

            stores_health.append(
                StoreHealth(
                    store_id=store_id,
                    last_event_timestamp=last_ts,
                    status=status,
                )
            )
    except Exception:
        pass

    # Overall system health status
    overall = "healthy"
    if any(v == "unhealthy" for v in components.values()):
        overall = "unhealthy"
    elif any(s.status == "STALE_FEED" for s in stores_health):
        overall = "degraded"

    uptime = time.time() - start_time

    return HealthResponse(
        status=overall,
        components=components,
        uptime_seconds=round(uptime, 1),
        stores=stores_health,
        events_processed=consumer.events_consumed,
    )
