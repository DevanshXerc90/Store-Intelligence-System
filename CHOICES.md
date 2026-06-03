# Engineering Choices & Trade-Offs

This document covers three key decisions as required by the challenge rubric, plus additional trade-offs made during implementation. For each of the three primary decisions: options considered, what AI suggested, and what was chosen.

---

## Decision 1: Detection Model Selection

**Options Considered**:

| Model | Speed (FPS on CPU) | mAP (COCO) | Notes |
|-------|-------------------|-------------|-------|
| YOLOv8n (nano) | ~45 FPS | 37.3 | Smallest YOLO variant. Fastest inference. |
| YOLOv8s (small) | ~25 FPS | 44.9 | Better accuracy, 2× slower. |
| YOLOv9-C | ~15 FPS | 53.0 | State-of-the-art accuracy, heavy. |
| RT-DETR-L | ~12 FPS | 53.0 | Transformer-based, high accuracy, GPU-hungry. |
| MediaPipe Pose | ~30 FPS | N/A | Pose estimation, not detection. No built-in tracking. |

**What AI Suggested**: The LLM recommended YOLOv8s as the "best balance" of speed and accuracy, noting that the small variant's higher mAP (44.9 vs 37.3) would improve group detection and partial occlusion handling.

**What I Chose**: **YOLOv8n (nano)** — and disagreed with the AI's recommendation.

**Why**: In retail CCTV at 1080p with decent lighting, person detection is not the hard problem — tracking continuity is. YOLOv8n's 37.3 mAP is more than sufficient for detecting standing/walking humans in a well-lit store. The real challenge is maintaining stable track IDs across frames, which depends on the tracker (ByteTrack), not the detector's mAP. YOLOv8n runs at ~45 FPS on CPU, which means the detector container can process 20-minute clips in reasonable time without requiring a GPU. Using YOLOv8s would double processing time for a marginal improvement that doesn't affect the business metrics (entry/exit counts, zone dwell).

Additionally, ByteTrack's built-in integration with Ultralytics YOLOv8 (`model.track(persist=True, tracker="bytetrack.yaml")`) eliminates the need for custom tracker wiring. This was a strong practical advantage over RT-DETR or MediaPipe, which would have required manual DeepSORT/StrongSORT integration.

---

## Decision 2: Event Schema Design

**Options Considered**:

1. **Flat schema**: One event type per row, all fields present (nullable for irrelevant fields). Simple to query, verbose storage.
2. **Polymorphic schema**: A base event with a `metadata` JSON blob for type-specific fields. Flexible, harder to validate.
3. **Separate tables per event type**: `entries`, `exits`, `zone_dwells`, `billing_events`. Normalised, but complex joins for session building.

**What AI Suggested**: The LLM suggested option 2 (polymorphic with JSON metadata) because it "matches the challenge's sample schema exactly" and is the most extensible for future event types.

**What I Chose**: **Option 1 — Flat schema with Pydantic pre-validation**, but with a critical addition the AI didn't suggest.

**Why**: The challenge schema uses a flat structure with nullable fields (`queue_depth: null` for non-billing events, `dwell_ms: 0` for instantaneous events). A flat schema maps directly to SQLite columns, making SQL queries for metrics/funnel/heatmap straightforward — no JSON extraction needed.

The critical addition was the Pydantic `@model_validator(mode="before")` normaliser. The sample_events.jsonl used entirely different field names from the canonical schema (`store_code` vs `store_id`, `id_token` vs `visitor_id`, `event_timestamp` vs `timestamp`). Rather than maintaining two schemas, the pre-validator maps all known aliases to canonical names before validation. This means the same `POST /events/ingest` endpoint accepts both the detector's raw output and the organiser's sample format without any caller-side transformation. The AI initially suggested handling this with separate Pydantic models and a factory pattern — I rejected that as over-engineered for a known, finite set of aliases.

---

## Decision 3: API Architecture — SQLite over PostgreSQL

**Options Considered**:

1. **PostgreSQL**: Full ACID, concurrent writes, production-standard. Requires an additional Docker service.
2. **SQLite (WAL mode)**: Single-file, zero-config, concurrent reads, serialised writes. No extra container.
3. **Redis only**: Store everything in Redis hashes/streams. Fast, but no durable query surface.

**What AI Suggested**: The LLM strongly recommended PostgreSQL, citing that "a production system handling 40 stores needs proper concurrent write support" and that SQLite would become a bottleneck.

**What I Chose**: **SQLite in WAL mode** — and disagreed with the AI.

**Why**: This is a take-home challenge, not a production deployment. The acceptance gate is `docker compose up` with no manual steps. Adding PostgreSQL means:
- An additional Docker service with health checks and startup ordering
- Database migration scripts or init SQL
- Connection pooling configuration
- A heavier Docker image

SQLite in WAL (Write-Ahead Logging) mode supports concurrent reads from the API threads while the background consumer thread writes events. For the scale of this challenge (2 stores, ~1000 events per 20-minute clip), SQLite handles the load trivially. The write serialisation is not a bottleneck because event ingestion is batched (up to 500 events per POST) and the consumer processes Redis stream entries sequentially.

If this were a production system at 40 stores with real-time event rates, I would switch to PostgreSQL (or TimescaleDB for time-series queries). But for a challenge where simplicity and "it just works on `docker compose up`" are scored, SQLite is the right trade-off.

---

## Additional Trade-Offs

### 4. POS Correlation: Time-Window vs. Identity Matching

**Choice**: 5-minute billing-zone-prerequisite time window correlation.

**Reasoning**: The POS CSV has no `customer_id`, so correlation must be inferred. A visitor is only a conversion candidate if they have a `BILLING_QUEUE_JOIN` event, and a POS transaction within 5 minutes of their billing zone entry counts as a purchase. Matched transaction IDs are tracked to prevent double-counting. This is more precise than a naive "any visitor near exit time" approach.

### 5. Session-Scoped Funnel (4 Stages)

**Choice**: Entry → Zone Visit → Billing Queue → Purchase. The unit is the visitor session, not raw events.

**Reasoning**: Using sessions ensures re-entries don't inflate counts. The funnel reports both absolute counts and relative drop-off percentages between stages, making it actionable for store managers.

### 6. Heatmap Normalisation & Confidence

**Choice**: Zone visit frequency normalised 0–100 relative to the highest-traffic zone. `data_confidence: "LOW"` flag when total sessions < 20.

**Reasoning**: Normalisation makes zone scores comparable regardless of absolute traffic volume. The confidence flag prevents business decisions based on statistically insignificant data.

### 7. Structured Logging Middleware

**Choice**: FastAPI middleware logs `trace_id`, `store_id`, `endpoint`, `latency_ms`, `event_count`, and `status_code` for every request.

**Reasoning**: The challenge scores "production readiness" at 20 points. Structured logs with trace IDs make debugging straightforward for on-call engineers. Custom exception handlers for `sqlite3.Error` and `redis.RedisError` return `503 Service Unavailable` with structured bodies — no raw stack traces leak to clients.
