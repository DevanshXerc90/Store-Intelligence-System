"""
Shared data schemas for the Store Intelligence System.
Uses Pydantic v2 for validation and serialization.

Aligned with the updated Purplle Tech Challenge specification:
- Multi-store support via store_id
- visitor_id (Re-ID token) instead of track_id
- New event types: ZONE_ENTER, ZONE_EXIT, BILLING_QUEUE_JOIN, etc.
- dwell_ms (milliseconds) instead of dwell_seconds
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ──────────────────────────────────────────────────────────


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class AnomalySeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    BILLING_QUEUE_SPIKE = "BILLING_QUEUE_SPIKE"
    CONVERSION_DROP = "CONVERSION_DROP"
    DEAD_ZONE = "DEAD_ZONE"
    UNUSUAL_TRAFFIC = "UNUSUAL_TRAFFIC"
    STALE_FEED = "STALE_FEED"


# ── Event Ingest Schemas ───────────────────────────────────────────


class EventMetadata(BaseModel):
    """Metadata sub-object within each event."""
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None
    # Allow additional arbitrary keys from detection pipeline
    model_config = {"extra": "allow"}


class StoreEvent(BaseModel):
    """
    A single detection/tracking event — the canonical schema.

    Matches the challenge doc's required output format:
    event_id, store_id, camera_id, visitor_id, event_type,
    timestamp, zone_id, dwell_ms, is_staff, confidence, metadata
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id: str
    camera_id: str
    visitor_id: str = ""  # Re-ID token, e.g. "VIS_c8a2f1"
    event_type: str  # Accept string to allow flexible ingest + validation
    timestamp: str  # ISO-8601 UTC
    zone_id: Optional[str] = None
    dwell_ms: Optional[int] = None  # duration in milliseconds; 0 for instantaneous
    is_staff: bool = False
    confidence: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalise_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Normalise store_id
        if "store_id" not in data and "store_code" in data:
            data["store_id"] = data["store_code"]
        if "store_id" in data and isinstance(data["store_id"], str):
            data["store_id"] = data["store_id"].upper()

        # 2. Normalise visitor_id
        if "visitor_id" not in data or not data["visitor_id"]:
            if "id_token" in data and data["id_token"]:
                data["visitor_id"] = str(data["id_token"])
            elif "track_id" in data and data["track_id"]:
                data["visitor_id"] = f"VIS_{data['track_id']}"

        # 3. Normalise timestamp
        if "timestamp" not in data or not data["timestamp"]:
            for ts_key in ["event_timestamp", "event_time", "queue_join_ts", "timestamp"]:
                if ts_key in data and data[ts_key]:
                    data["timestamp"] = data[ts_key]
                    break

        # 4. Normalise event_type
        et = data.get("event_type", "")
        if isinstance(et, str):
            et_lower = et.lower()
            if et_lower == "entry":
                data["event_type"] = "ENTRY"
            elif et_lower == "exit":
                data["event_type"] = "EXIT"
            elif et_lower in ("zone_entered", "zone_enter"):
                data["event_type"] = "ZONE_ENTER"
            elif et_lower in ("zone_exited", "zone_exit"):
                data["event_type"] = "ZONE_EXIT"
            elif et_lower == "queue_completed":
                # Check if it was abandoned (e.g. wait_seconds > threshold or explicitly flag)
                if data.get("abandoned") is True:
                    data["event_type"] = "BILLING_QUEUE_ABANDON"
                else:
                    data["event_type"] = "ZONE_DWELL"
                    data["zone_id"] = data.get("zone_id") or "BILLING"
                    if "wait_seconds" in data and data["wait_seconds"] is not None:
                        data["dwell_ms"] = int(float(data["wait_seconds"]) * 1000)
            elif et_lower == "queue_abandoned" or (et_lower == "queue_completed" and data.get("abandoned") is True):
                data["event_type"] = "BILLING_QUEUE_ABANDON"
                if "wait_seconds" in data and data["wait_seconds"] is not None:
                    data["dwell_ms"] = int(float(data["wait_seconds"]) * 1000)
            elif et_lower in ("queue_join", "billing_queue_join"):
                data["event_type"] = "BILLING_QUEUE_JOIN"
            elif et_lower == "reentry":
                data["event_type"] = "REENTRY"
            else:
                data["event_type"] = et.upper()

        # 5. Normalise dwell_ms
        if "dwell_ms" not in data or data["dwell_ms"] is None:
            if "dwell_seconds" in data and data["dwell_seconds"] is not None:
                data["dwell_ms"] = int(float(data["dwell_seconds"]) * 1000)
            elif "wait_seconds" in data and data["wait_seconds"] is not None:
                data["dwell_ms"] = int(float(data["wait_seconds"]) * 1000)
            else:
                data["dwell_ms"] = 0

        # 6. Populate metadata with other fields for compatibility
        metadata = data.setdefault("metadata", {})
        for k in ["queue_depth", "sku_zone", "session_seq", "queue_position_at_join", "wait_seconds", "abandoned", "age_pred", "gender_pred", "age_bucket", "is_face_hidden", "group_id", "group_size"]:
            if k in data and data[k] is not None:
                metadata[k] = data[k]

        return data


# ── Ingest Request / Response ──────────────────────────────────────


class IngestRequest(BaseModel):
    """POST /events/ingest — batch of up to 500 events."""
    events: list[StoreEvent] = Field(..., max_length=500)


class IngestError(BaseModel):
    """Detail about a single rejected event."""
    index: int
    event_id: Optional[str] = None
    error: str


class IngestResponse(BaseModel):
    """Response from POST /events/ingest."""
    accepted: int
    rejected: int
    duplicates: int
    errors: list[IngestError] = []


# ── Session Schema ─────────────────────────────────────────────────


class CustomerSession(BaseModel):
    """A customer visit session (ENTRY → EXIT)."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    visitor_id: str
    store_id: str
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    is_staff: bool = False
    is_complete: bool = True
    is_reentry: bool = False
    zones_visited: list[str] = Field(default_factory=list)
    zone_dwells: dict[str, float] = Field(default_factory=dict)  # zone_id -> total dwell_ms
    max_dwell_zone: Optional[str] = None
    max_dwell_ms: Optional[int] = None
    reached_billing: bool = False
    purchased: bool = False
    matched_transaction_id: Optional[str] = None


# ── API Response Schemas ───────────────────────────────────────────


class ZoneDwell(BaseModel):
    """Avg dwell per zone — used in metrics response."""
    zone_id: str
    zone_name: Optional[str] = None
    avg_dwell_ms: int
    visit_count: int


class MetricsResponse(BaseModel):
    store_id: str
    date: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_per_zone: list[ZoneDwell] = []
    queue_depth: Optional[int] = None  # current or latest queue depth
    abandonment_rate: float = 0.0
    total_transactions: int = 0
    total_revenue: float = 0.0
    staff_count: int = 0
    peak_hour: Optional[str] = None


class FunnelStage(BaseModel):
    stage: str
    count: int
    pct: float
    drop_off_pct: Optional[float] = None


class FunnelResponse(BaseModel):
    store_id: str
    date: str
    funnel: list[FunnelStage]


class HeatmapZone(BaseModel):
    zone_id: str
    zone_name: Optional[str] = None
    visit_count: int
    avg_dwell_ms: int
    normalised_score: float = 0.0  # 0–100
    data_confidence: Optional[str] = None  # "LOW" if < 20 sessions


class HeatmapResponse(BaseModel):
    store_id: str
    date: str
    zones: list[HeatmapZone]
    total_sessions: int
    data_confidence: Optional[str] = None  # overall flag


class AnomalyRecord(BaseModel):
    anomaly_id: str
    anomaly_type: str
    severity: str  # INFO / WARN / CRITICAL
    description: str
    suggested_action: str = ""
    timestamp: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class AnomaliesResponse(BaseModel):
    store_id: str
    date: str
    total_anomalies: int
    anomalies: list[AnomalyRecord]


class StoreHealth(BaseModel):
    store_id: str
    last_event_timestamp: Optional[str] = None
    status: str = "OK"  # OK / STALE_FEED


class HealthResponse(BaseModel):
    status: str
    components: dict[str, str]
    uptime_seconds: float
    stores: list[StoreHealth] = []
    events_processed: int
