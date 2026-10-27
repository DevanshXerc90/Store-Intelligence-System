# Store Intelligence System

AI-powered store analytics combining CCTV computer vision with POS data for real-time business intelligence across multiple stores.

- **Live Public Demo**: [https://5befa08c77882b.lhr.life/dashboard](https://5befa08c77882b.lhr.life/dashboard)
- **Stores Supported**: Store 1 (ST1076/STORE_1) and Store 2 (STORE_2)
- **Acceptance Gate Target**: `GET /stores/STORE_BLR_002/metrics`

## Quick Start

```bash
# 1. Clone and enter the project
cd purplle

# 2. Start the system (Redis, Ingestion, API, and background Video Processing)
docker compose up --build -d

# 3. Access health check to watch video processing progress
curl http://localhost:8000/health

# 4. Access the intelligence API endpoints (replace store_id as needed)
curl http://localhost:8000/stores/STORE_BLR_002/metrics
curl http://localhost:8000/stores/STORE_BLR_002/funnel
curl http://localhost:8000/stores/STORE_BLR_002/heatmap
curl http://localhost:8000/stores/STORE_BLR_002/anomalies

# 5. Ingest events (supports batching up to 500 events, idempotent)
curl -X POST http://localhost:8000/events/ingest -H "Content-Type: application/json" -d @data/sample_payload.json

# 6. Interactive API docs
open http://localhost:8000/docs
```

## Running Correctness Assertions

To run the 10 automated correctness test assertions against the live running API:

```bash
pip install requests
python assertions.py
```

## Running Tests

```bash
# Locally (requires Python 3.12+)
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Architecture

```
┌────────────┐    ┌──────────────┐    ┌──────────────┐
│   Redis    │◄───│   Detector   │    │   API        │
│   Streams  │    │  YOLOv8n +   │    │  FastAPI +   │
│            │───►│  ByteTrack   │    │  Consumer    │
└────────────┘    └──────────────┘    └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │   SQLite DB   │
                                      └──────────────┘
```

- **Redis**: Streaming queue bus for detection events.
- **Detector**: Person detection, tracking, line-crossing, and zone analysis. Scans video directories recursively and maps cameras dynamically per store.
- **API**: Serves REST endpoints, runs background session builder, performs POS temporal matching, and checks for operational anomalies.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service status, last event timestamp per store, STALE_FEED alerts |
| `/dashboard` | GET | Interactive, premium real-time Store Intelligence Dashboard (KPIs, Funnel, Heatmap, Alerts, Live Stream) |
| `/stores/{store_id}/metrics` | GET | Today's unique visitors, conversion rate, zone dwell, queue depth, abandonment rate |
| `/stores/{store_id}/funnel` | GET | Customer journey: Entry → Zone Visit → Billing Queue → Purchase (with counts and drop-offs) |
| `/stores/{store_id}/heatmap` | GET | Normalised zone traffic score (0-100) and data confidence scoring |
| `/stores/{store_id}/anomalies` | GET | Active alerts (BILLING_QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE) with suggested actions |
| `/events/ingest` | POST | Batch event ingestion with idempotency and partial-success responses |
| `/docs` | GET | Swagger interactive API docs |

## Layout and Cameras

The detector automatically parses layout files and maps video files recursively inside `data/videos`:

### Store 1 (`STORE_1` / `ST1076`)
- `CAM 3 - entry.mp4` -> Entrance threshold
- `CAM 1 - zone.mp4` -> Skincare aisle
- `CAM 2 - zone.mp4` -> Makeup aisle
- `CAM 5 - billing.mp4` -> Billing counter

### Store 2 (`STORE_2`)
- `entry 1.mp4` / `entry 2.mp4` -> Cross-camera entrance thresholds
- `zone.mp4` -> Floor shopping zone
- `billing_area.mp4` -> Billing area

## Tech Stack

- **Detection**: YOLOv8n + ByteTrack (Ultralytics)
- **API**: FastAPI + Uvicorn
- **Streaming Queue**: Redis 7
- **Database**: SQLite (WAL mode, multi-threaded)
- **Container**: Docker Compose
- **Language**: Python 3.12
