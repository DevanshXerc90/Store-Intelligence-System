"""
FastAPI application — main entry point for the API service.

Handles:
1. Loading sales CSV data into SQLite on startup
2. Starting the Redis event consumer as a background task
3. Building sessions and detecting anomalies after CCTV processing completes
4. Serving all API endpoints
"""
import csv
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import redis
import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import Config
from src.database import Database
from src.processor.event_consumer import EventConsumer
from src.processor.session_builder import SessionBuilder
from src.processor.anomaly_detector import AnomalyDetector
from src.api.routes import metrics, funnel, anomalies, ingest, health, heatmap

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger("api")


def load_sales_data(db: Database) -> None:
    """Load sales CSV into the database."""
    csv_path = Path(Config.SALES_CSV)
    if not csv_path.exists():
        logger.warning("api.sales_csv_not_found", path=str(csv_path))
        return

    logger.info("api.loading_sales", path=str(csv_path))

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                try:
                    db.insert_sale(
                        {
                            "order_id": row.get("order_id", "").strip(),
                            "order_date": row.get("order_date", "").strip(),
                            "order_time": row.get("order_time", "").strip(),
                            "store_id": row.get("store_id", "").strip(),
                            "product_id": row.get("product_id", "").strip(),
                            "brand_name": row.get("brand_name", "").strip(),
                            "total_amount": float(row.get("total_amount", 0.0) or 0.0),
                        }
                    )
                    count += 1
                except (ValueError, TypeError) as e:
                    logger.warning("api.sale_parse_error", row=row.get("order_id"), error=str(e))

        logger.info("api.sales_loaded", count=count)
    except Exception as e:
        logger.error("api.sales_load_failed", error=str(e))


def post_processing_worker(db: Database, consumer: EventConsumer) -> None:
    """
    Background worker that waits for detection to complete,
    then builds sessions and runs anomaly detection.
    """
    logger.info("post_processor.waiting_for_detection")

    # Check if detection already completed (e.g., on restart)
    if db.is_processing_complete() and db.get_total_events() > 0:
        logger.info("post_processor.detection_already_complete_in_db")
        consumer.detection_complete = True
    else:
        # Wait for detection to complete (poll every 5 seconds)
        timeout = 3600  # 1 hour max
        elapsed = 0
        while elapsed < timeout:
            if consumer.detection_complete:
                break
            # Also check DB in case we missed the Redis signal
            if db.is_processing_complete() and db.get_total_events() > 0:
                consumer.detection_complete = True
                break
            time.sleep(5)
            elapsed += 5

        if not consumer.detection_complete:
            logger.warning("post_processor.timeout", elapsed=elapsed)
            if db.get_total_events() == 0:
                logger.warning("post_processor.no_events")
                return

    # Wait a bit for remaining events to be consumed
    time.sleep(3)

    # Deduplicate events before building sessions
    try:
        removed = db.deduplicate_events()
        if removed > 0:
            logger.info("post_processor.deduplication", removed=removed)
    except Exception as e:
        logger.error("post_processor.dedup_error", error=str(e))

    # Check if sessions already built (avoid re-running on restart)
    existing_sessions = db.get_session_count(include_staff=True)
    if existing_sessions > 0:
        logger.info("post_processor.sessions_already_exist", count=existing_sessions)
    else:
        logger.info("post_processor.building_sessions")
        try:
            builder = SessionBuilder(db)
            sessions = builder.build_sessions()
            logger.info("post_processor.sessions_built", count=len(sessions))
        except Exception as e:
            logger.error("post_processor.session_error", error=str(e))

    # Check if anomalies already detected
    existing_anomalies = db.get_anomalies()
    if existing_anomalies:
        logger.info("post_processor.anomalies_already_exist", count=len(existing_anomalies))
    else:
        logger.info("post_processor.detecting_anomalies")
        try:
            detector = AnomalyDetector(db)
            anomaly_list = detector.run_detection()
            logger.info("post_processor.anomalies_detected", count=len(anomaly_list))
        except Exception as e:
            logger.error("post_processor.anomaly_error", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # ── Startup ──────────────────────────────────────────────────
    logger.info("api.starting", host=Config.API_HOST, port=Config.API_PORT)

    # Initialize database
    if not hasattr(app.state, "db") or app.state.db is None:
        db = Database()
        app.state.db = db
        # Reset transient data from any previous run.
        db.reset_for_reprocessing()
        # Load sales data
        load_sales_data(db)
    else:
        db = app.state.db

    app.state.start_time = time.time()

    # Start event consumer
    if not hasattr(app.state, "consumer") or app.state.consumer is None:
        consumer = EventConsumer(db)
        consumer.start()
        app.state.consumer = consumer
    else:
        consumer = app.state.consumer

    # Start post-processing worker in background
    worker = threading.Thread(
        target=post_processing_worker, args=(db, consumer), daemon=True
    )
    worker.start()

    logger.info("api.ready")

    yield

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("api.shutting_down")
    if hasattr(consumer, "stop"):
        consumer.stop()


# Create FastAPI app
app = FastAPI(
    title="Purplle Store Intelligence API",
    description=(
        "AI-powered store analytics combining CCTV computer vision "
        "with POS data for real-time business intelligence. "
        "Brigade Road, Bangalore — Store ST1008."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(sqlite3.Error)
async def sqlite_exception_handler(request: Request, exc: sqlite3.Error):
    logger.error("database.error", error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "Database service is temporarily unavailable"},
    )


@app.exception_handler(redis.RedisError)
async def redis_exception_handler(request: Request, exc: redis.RedisError):
    logger.error("redis.error", error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "Cache service is temporarily unavailable"},
    )


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    request.state.trace_id = trace_id

    # Extract store_id from path /stores/{store_id}/...
    store_id = None
    path_parts = request.url.path.strip("/").split("/")
    if len(path_parts) >= 2 and path_parts[0] == "stores":
        store_id = path_parts[1]

    start_time = time.time()
    response = await call_next(request)
    latency_ms = round((time.time() - start_time) * 1000, 2)

    # Get event_count if set in request state
    event_count = getattr(request.state, "event_count", None)

    # Log in structured format
    logger.info(
        "request.processed",
        trace_id=trace_id,
        store_id=store_id,
        endpoint=request.url.path,
        latency_ms=latency_ms,
        event_count=event_count,
        status_code=response.status_code,
    )

    response.headers["X-Trace-Id"] = trace_id
    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)
app.include_router(ingest.router)


@app.get("/", tags=["Root"])
async def root():
    """API root — system overview."""
    return {
        "system": "Purplle Store Intelligence",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "metrics": "/stores/{store_id}/metrics",
            "funnel": "/stores/{store_id}/funnel",
            "heatmap": "/stores/{store_id}/heatmap",
            "anomalies": "/stores/{store_id}/anomalies",
            "ingest": "/events/ingest",
            "docs": "/docs",
        },
    }


def main():
    """Entry point for the API service."""
    uvicorn.run(
        "src.api.main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
