# Store Intelligence System — Architecture & Design

## System Overview

An AI-powered Store Intelligence System that processes CCTV footage recursively from multiple retail stores to generate actionable business metrics: footfall counting, time-based POS conversion rate, simplified session-based conversion funnels, normalized zone heatmaps, and operational anomaly detection.

## Multi-Store Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        docker compose up                                │
│ ├──────────────────┬──────────────────────────┬──────────────────────────┤
│ │    Redis 7       │     Detector Service     │      API Service         │
│ │    (Alpine)      │                          │                          │
│ │                  │  ┌──────────────────┐    │  ┌──────────────────┐   │
│ │  Event Stream    │  │  YOLOv8n Model   │    │  │  FastAPI Server  │   │
│ │  ─────────────   │  │  (Person Det.)   │    │  │  Port 8000       │   │
│ │  store:events    │  └────────┬─────────┘    │  └────────┬─────────┘   │
│ │                  │           │              │           │              │
│ │                  │  ┌────────▼─────────┐    │  ┌────────▼─────────┐   │
│ │                  │  │  ByteTrack       │    │  │  Event Consumer  │   │
│ │                  │  │  (Multi-Object)  │    │  │  (Redis → SQLite)│   │
│ │                  │  └────────┬─────────┘    │  └────────┬─────────┘   │
│ │                  │           │              │           │              │
│ │                  │  ┌────────▼─────────┐    │  ┌────────▼─────────┐   │
│ │                  │  │ Line Crossing    │    │  │ Session Builder  │   │
│ │  ◄───────────────┤──│ (Entry/Exit)     │    │  │ Anomaly Detector │   │
│ │                  │  │ Zone Analyzer    │    │  │                  │   │
│ │                  │  └──────────────────┘    │  └────────┬─────────┘   │
│ │                  │                          │           │              │
│ │                  │                          │  ┌────────▼─────────┐   │
│ │                  │                          │  │   SQLite DB      │   │
│ │                  │                          │  │  (WAL mode)      │   │
│ │                  │                          │  └──────────────────┘   │
└───────┴──────────────────────────┴──────────────────────────┘
```

## Data Flow

```
CCTV Videos (Recursive directories per store)
    │
    ▼
┌─────────────────────────────────────┐
│  Detector Service                    │
│                                      │
│  For each store and camera:          │
│  1. Parse store_id from parent folder│
│  2. Sample at 5 FPS                  │
│  3. YOLOv8n + ByteTrack tracking     │
│  4. Entrance cameras -> ENTRY/EXIT   │
│  5. Zone cameras -> ZONE_DWELL (ms)  │
│  All -> Publish events to Redis      │
└────────────────┬────────────────────┘
                 │ Redis Streams
                 ▼
┌─────────────────────────────────────┐
│  API Service                         │
│                                      │
│  1. Consume events -> SQLite         │
│  2. Load sales CSV -> SQLite         │
│  3. Build customer sessions          │
│  4. Run anomaly detection            │
│  5. Serve REST API endpoints         │
│                                      │
│  GET /health                         │
│  GET /stores/{id}/metrics            │
│  GET /stores/{id}/funnel             │
│  GET /stores/{id}/heatmap            │
│  GET /stores/{id}/anomalies          │
│  POST /events/ingest                 │
└─────────────────────────────────────┘
```

## Camera Layout and Mapping

### Store 1 (`STORE_1` / `ST1076`)
- `CAM 3 - entry.mp4` -> Entrance threshold (ENTRY / EXIT)
- `CAM 1 - zone.mp4` -> Skincare zone (ZONE_DWELL)
- `CAM 2 - zone.mp4` -> Makeup zone (ZONE_DWELL)
- `CAM 5 - billing.mp4` -> Billing counter (BILLING)

### Store 2 (`STORE_2`)
- `entry 1.mp4` / `entry 2.mp4` -> Entrance thresholds (ENTRY / EXIT)
- `zone.mp4` -> Makeup floor zone (ZONE_DWELL)
- `billing_area.mp4` -> Billing area counter (BILLING)

## Ingestion Normalization & Schemas

The `POST /events/ingest` and Redis stream consumer normalize both raw detector outputs and organizer formats:
1. `store_code` or `store_id` -> mapped to canonical `store_id` (upper-cased)
2. `id_token` or `track_id` -> mapped to unique visitor token `visitor_id` (prefixed with `VIS_`)
3. `event_timestamp`, `event_time`, `queue_join_ts` -> mapped to standard ISO `timestamp`
4. `dwell_seconds` or `wait_seconds` -> accumulated to `dwell_ms` (milliseconds)
5. `event_type` -> mapped to `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`

## Conversion Funnel Stages

The funnel endpoint tracks traffic progression per visitor session:
1. **entry** — Unique visitor sessions (ENTRY / REENTRY)
2. **zone_visit** — Sessions with visits in at least one product zone
3. **billing_queue** — Sessions that entered the billing counter zone
4. **purchase** — Sessions matched to a POS order via time correlation

## Anomaly Detection

| Anomaly Type | Condition | Severity | Suggested Action |
|--------------|-----------|----------|------------------|
| `BILLING_QUEUE_SPIKE` | Billing queue depth >= 5 | WARN / CRITICAL | Open additional billing counters immediately. |
| `CONVERSION_DROP` | Store conversion rate < 15% | WARN / CRITICAL | Inspect checkout queue times and checkout bottlenecks. |
| `DEAD_ZONE` | No traffic in zone for >= 30 min | INFO | Inspect zone displays, lighting, or signs. |
| `UNUSUAL_TRAFFIC` | Entry outside hours (10AM - 10PM) | CRITICAL | Verify security log and check store lock status. |

---

## AI-Assisted Decisions

This section documents three specific places where an LLM shaped the system design, and whether the suggestion was accepted or overridden.

### 1. Event Schema Normalisation Strategy — **Agreed with AI, extended scope**

**Context**: The sample_events.jsonl used field names (`store_code`, `id_token`, `event_timestamp`) that differed from the canonical schema in the problem statement (`store_id`, `visitor_id`, `timestamp`).

**AI Suggestion**: The LLM recommended implementing a Pydantic `@model_validator(mode="before")` to normalise incoming field names before validation, rather than maintaining separate schemas or using manual if/else mapping.

**Decision**: Agreed — but extended the validator beyond what the LLM initially suggested. The AI's first draft only handled `store_code → store_id`. I added mappings for `id_token → visitor_id`, `event_time / queue_join_ts → timestamp`, `dwell_seconds / wait_seconds → dwell_ms` (with unit conversion), and event type canonicalisation (e.g. `queue_join → BILLING_QUEUE_JOIN`). This single validator now handles every format variant found in both the organiser's sample data and the detector's raw output.

### 2. POS Correlation Without Customer ID — **Overrode AI's initial approach**

**Context**: The POS CSV has no `customer_id` column, so conversion correlation must be inferred.

**AI Suggestion**: The LLM initially proposed correlating by matching the closest POS transaction timestamp to any visitor's exit time within the same store — essentially a nearest-neighbour join on timestamps.

**Decision**: Overrode. The exit-time approach would incorrectly match visitors who never went near billing. Instead, I implemented a billing-zone-prerequisite model: only visitors who have a `BILLING_QUEUE_JOIN` event are candidates for POS matching, and the correlation window is the 5 minutes *after* they joined the billing zone (not after exit). This prevents false conversions from visitors who browsed but never queued. Matched transaction IDs are tracked in a set to prevent double-counting.

### 3. Line Crossing Direction Detection — **Agreed with AI**

**Context**: Determining entry vs. exit direction from a virtual line requires tracking position history per track ID.

**AI Suggestion**: The LLM suggested a hysteresis-based approach: maintain the last-known side (above/below the line) for each track ID, and only emit a crossing event when the person moves past the line *plus* a hysteresis margin (±20 pixels). This prevents flicker when someone stands near the threshold.

**Decision**: Agreed — the hysteresis approach is standard in production line-crossing systems. I also added a `min_frames` parameter (default 2) so that at least two consecutive frames must show the person on the new side before a crossing is confirmed. This eliminates single-frame jitter from tracking noise.

