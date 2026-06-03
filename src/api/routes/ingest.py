"""
POST /events/ingest — Batch event ingestion endpoint.

Accepts batches of up to 500 events.
Idempotent by event_id — safe to call twice with the same payload.
Partial success: malformed events are rejected with structured errors.
"""
import uuid

import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import ValidationError

from src.schemas import StoreEvent, IngestRequest, IngestResponse, IngestError

logger = structlog.get_logger("api.ingest")

router = APIRouter()


@router.post("/events/ingest", response_model=IngestResponse, tags=["Ingest"])
async def ingest_events(request: Request, body: IngestRequest):
    request.state.event_count = len(body.events)
    db = request.app.state.db

    accepted = 0
    rejected = 0
    duplicates = 0
    errors = []

    for idx, event in enumerate(body.events):
        try:
            # Ensure event_id is set
            if not event.event_id:
                event.event_id = str(uuid.uuid4())

            # Convert to dict for storage
            event_dict = {
                "event_id": event.event_id,
                "store_id": event.store_id,
                "camera_id": event.camera_id,
                "visitor_id": event.visitor_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "zone_id": event.zone_id,
                "dwell_ms": event.dwell_ms,
                "is_staff": event.is_staff,
                "confidence": event.confidence,
                "metadata": event.metadata,
            }

            # Insert (returns False if duplicate)
            inserted = db.insert_event(event_dict)
            if inserted:
                accepted += 1
            else:
                duplicates += 1

        except Exception as e:
            rejected += 1
            errors.append(
                IngestError(
                    index=idx,
                    event_id=getattr(event, "event_id", None),
                    error=str(e),
                )
            )

    logger.info(
        "ingest.batch_processed",
        accepted=accepted,
        rejected=rejected,
        duplicates=duplicates,
        total=len(body.events),
    )

    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        duplicates=duplicates,
        errors=errors,
    )
