"""
GET /events — Paginated event log endpoint.

Returns raw detection events with optional filtering by
camera, event type, and pagination support.
"""
from typing import Optional

from fastapi import APIRouter, Query, Request

from src.schemas import EventsResponse, EventRecord

router = APIRouter()


@router.get("/events", response_model=EventsResponse, tags=["Events"])
async def get_events(
    request: Request,
    camera: Optional[str] = Query(None, description="Filter by camera ID (e.g., CAM_3)"),
    type: Optional[str] = Query(None, description="Filter by event type (entry, exit, zone_dwell)"),
    limit: int = Query(50, ge=1, le=500, description="Number of events per page"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """
    Returns paginated event log with optional filters.

    Events are ordered by timestamp (ascending).
    """
    db = request.app.state.db

    offset = (page - 1) * limit

    raw_events = db.get_events(
        event_type=type,
        camera_id=camera,
        limit=limit,
        offset=offset,
    )

    total = db.get_event_count(event_type=type, camera_id=camera)

    events = [
        EventRecord(
            event_id=e["event_id"],
            event_type=e["event_type"],
            timestamp=e["timestamp"],
            camera_id=e["camera_id"],
            track_id=e.get("track_id"),
            is_staff=bool(e.get("is_staff")),
            direction=e.get("direction"),
            confidence=e.get("confidence"),
            zone=e.get("zone"),
            dwell_seconds=e.get("dwell_seconds"),
        )
        for e in raw_events
    ]

    return EventsResponse(
        total=total,
        page=page,
        page_size=limit,
        events=events,
    )
