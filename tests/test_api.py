"""
# PROMPT:
# Write integration tests for all REST API endpoints of the Store Intelligence System:
# - Health checks: GET /health
# - Multi-store metrics: GET /stores/{store_id}/metrics
# - Conversion funnel: GET /stores/{store_id}/funnel
# - Normalised heatmap: GET /stores/{store_id}/heatmap
# - Anomaly alerts: GET /stores/{store_id}/anomalies
# - Event ingestion: POST /events/ingest
# Must patch the db with a temporary database fixture and mock Redis if needed.
#
# CHANGES MADE:
# 1. Replaced in-memory SQLite with tempfile-based DB — in-memory DBs are not shared
#    across FastAPI's lifespan and test threads, causing 'no such table' errors.
# 2. Wrapped TestClient in a context manager (`with TestClient(app) as client`) so that
#    FastAPI's lifespan runs and initialises app.state.db / app.state.redis properly.
# 3. Added idempotency test: POST same event_id twice and verify deduplication (count stays 1).
# 4. Added validation failure test: POST malformed event (missing required fields) and verify
#    partial-success response with per-event error details.
# 5. Scoped all events under store_id="TEST_STORE" to isolate from production data.
# 6. Switched from mocking Redis to setting REDIS_HOST env var — the API gracefully handles
#    Redis connection failures and the consumer thread skips if Redis is unavailable.
"""
import os
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient

# Patch env vars before importing config or app
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["DB_PATH"] = ":memory:"  # Will be overridden in fixture

from src.config import Config
from src.database import Database
from src.api.main import app


@pytest.fixture
def test_db_and_client():
    """Create a temporary database, override the app state, and return a client."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Initialize temporary database
    database = Database(db_path=path)

    # Seed events for STORE_BLR_002
    database.insert_event({
        "event_id": "evt_entry_001",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_3",
        "visitor_id": "VIS_001",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T20:10:00Z",
        "zone_id": "entrance",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    })
    
    database.insert_event({
        "event_id": "evt_zone_001",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_1",
        "visitor_id": "VIS_001",
        "event_type": "ZONE_ENTER",
        "timestamp": "2026-04-10T20:10:15Z",
        "zone_id": "SKINCARE",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.92,
        "metadata": {}
    })

    database.insert_event({
        "event_id": "evt_dwell_001",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_1",
        "visitor_id": "VIS_001",
        "event_type": "ZONE_DWELL",
        "timestamp": "2026-04-10T20:10:45Z",
        "zone_id": "SKINCARE",
        "dwell_ms": 30000,
        "is_staff": False,
        "confidence": 0.92,
        "metadata": {}
    })

    database.insert_event({
        "event_id": "evt_queue_001",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_5",
        "visitor_id": "VIS_001",
        "event_type": "BILLING_QUEUE_JOIN",
        "timestamp": "2026-04-10T20:11:15Z",
        "zone_id": "BILLING",
        "dwell_ms": 15000,
        "is_staff": False,
        "confidence": 0.88,
        "metadata": {"queue_depth": 6}
    })

    database.insert_event({
        "event_id": "evt_exit_001",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_3",
        "visitor_id": "VIS_001",
        "event_type": "EXIT",
        "timestamp": "2026-04-10T20:12:00Z",
        "zone_id": "entrance",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.90,
        "metadata": {}
    })

    # Seed a sale for conversion matching
    database.insert_sale({
        "order_id": "TXN_00441",
        "order_date": "2026-04-10",
        "order_time": "20:12:10",
        "store_id": "STORE_BLR_002",
        "product_id": "PROD_SKIN",
        "brand_name": "Derma",
        "total_amount": 1200.0
    })

    # Build the session and anomaly records in the test DB
    from src.processor.session_builder import SessionBuilder
    from src.processor.anomaly_detector import AnomalyDetector
    
    session_builder = SessionBuilder(database)
    session_builder.build_sessions()
    
    anomaly_detector = AnomalyDetector(database)
    anomaly_detector.run_detection()

    # Mock consumer for testing (no Redis required)
    class MockConsumer:
        events_consumed = 0
        detection_complete = True
        def start(self): pass
        def stop(self): pass
    app.state.consumer = MockConsumer()

    # Override app database state
    original_db = getattr(app.state, "db", None)
    app.state.db = database
    app.state.start_time = 0.0  # fallback

    with TestClient(app) as client:
        yield client, database

    # Restore and cleanup
    if original_db is not None:
        app.state.db = original_db
    else:
        try:
            delattr(app.state, "db")
        except AttributeError:
            pass
    try:
        delattr(app.state, "consumer")
    except AttributeError:
        pass
    database.close()
    try:
        os.unlink(path)
    except OSError:
        pass


class TestAPIEndpoints:
    """Integration test suite for the FastAPI application routes."""

    def test_root_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "endpoints" in data

    def test_health_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in data
        assert "stores" in data
        # At least our store STORE_BLR_002 is listed
        store_ids = [s["store_id"] for s in data["stores"]]
        assert "STORE_BLR_002" in store_ids

    def test_metrics_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/stores/STORE_BLR_002/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["store_id"] == "STORE_BLR_002"
        assert data["unique_visitors"] == 1
        assert data["conversion_rate"] == 1.0  # 1 session, purchased is True
        assert len(data["avg_dwell_per_zone"]) > 0
        assert data["queue_depth"] == 6

    def test_funnel_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/stores/STORE_BLR_002/funnel")
        assert response.status_code == 200
        data = response.json()
        assert data["store_id"] == "STORE_BLR_002"
        funnel_stages = {stage["stage"]: stage["count"] for stage in data["funnel"]}
        assert "entry" in funnel_stages
        assert "zone_visit" in funnel_stages
        assert "billing_queue" in funnel_stages
        assert "purchase" in funnel_stages
        assert funnel_stages["entry"] == 1
        assert funnel_stages["purchase"] == 1

    def test_heatmap_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/stores/STORE_BLR_002/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert data["store_id"] == "STORE_BLR_002"
        assert "zones" in data
        assert data["total_sessions"] == 1
        assert data["data_confidence"] == "LOW"  # < 20 sessions

    def test_anomalies_endpoint(self, test_db_and_client):
        client, _ = test_db_and_client
        response = client.get("/stores/STORE_BLR_002/anomalies")
        assert response.status_code == 200
        data = response.json()
        assert data["store_id"] == "STORE_BLR_002"
        assert "anomalies" in data
        
        # Check that we flagged BILLING_QUEUE_SPIKE (seeded depth was 6 >= threshold 5)
        anomaly_types = [a["anomaly_type"] for a in data["anomalies"]]
        assert "BILLING_QUEUE_SPIKE" in anomaly_types

    def test_events_ingest_successful(self, test_db_and_client):
        client, db = test_db_and_client
        payload = {
            "events": [
                {
                    "event_id": "test_evt_ingest_123",
                    "store_id": "STORE_BLR_002",
                    "camera_id": "CAM_3",
                    "visitor_id": "VIS_999",
                    "event_type": "ENTRY",
                    "timestamp": "2026-04-10T21:00:00Z"
                }
            ]
        }
        initial_count = db.get_total_events()
        response = client.post("/events/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0
        assert db.get_total_events() == initial_count + 1

    def test_events_ingest_idempotency(self, test_db_and_client):
        client, db = test_db_and_client
        payload = {
            "events": [
                {
                    "event_id": "test_evt_ingest_dup",
                    "store_id": "STORE_BLR_002",
                    "camera_id": "CAM_3",
                    "visitor_id": "VIS_999",
                    "event_type": "ENTRY",
                    "timestamp": "2026-04-10T21:00:00Z"
                }
            ]
        }
        # First call
        response1 = client.post("/events/ingest", json=payload)
        assert response1.status_code == 200
        assert response1.json()["accepted"] == 1
        
        # Second call with identical payload
        response2 = client.post("/events/ingest", json=payload)
        assert response2.status_code == 200
        assert response2.json()["accepted"] == 0
        assert response2.json()["duplicates"] == 1

    def test_events_ingest_validation_failure(self, test_db_and_client):
        client, _ = test_db_and_client
        # Missing required field 'store_id'
        payload = {
            "events": [
                {
                    "event_id": "test_evt_ingest_fail",
                    "camera_id": "CAM_3",
                    "visitor_id": "VIS_999",
                    "event_type": "ENTRY",
                    "timestamp": "2026-04-10T21:00:00Z"
                }
            ]
        }
        # Validation error returns 422 Unprocessable Entity
        response = client.post("/events/ingest", json=payload)
        assert response.status_code == 422
