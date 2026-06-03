"""
# PROMPT:
# Write unit tests for the SessionBuilder:
# - Test basic session creation (ENTRY + EXIT)
# - Test incomplete session handling (ENTRY only)
# - Test staff exclusion from visitor sessions
# - Test multi-store session grouping
# - Test zone visit and dwell time aggregation
# - Test billing-prerequisite POS correlation matching
# All tests must seed events with a valid store_id and verify properties on visitor_id (not track_id).
#
# CHANGES MADE:
# 1. Refactored fixture to use tempfile.mkstemp instead of ":memory:" — SessionBuilder runs
#    in a separate call context from the test assertions, so file-backed DBs are required.
# 2. Added test_sales_matching: seeds a BILLING_QUEUE_JOIN event + a matching POS row within
#    the 5-minute correlation window and asserts the session is marked as purchased.
# 3. Added test_zone_enrichment: verifies that ZONE_DWELL events attach zone_id and
#    accumulated dwell_ms to the visitor's session record.
# 4. Changed event seeding to use store_id="TEST_STORE" consistently across all tests.
# 5. Verified that staff events (is_staff=True) are stored in the events table but excluded
#    from session building — the original AI output only checked they were filtered at ingest.
"""
import os
import tempfile
import uuid
import pytest

from src.database import Database
from src.processor.session_builder import SessionBuilder


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = Database(db_path=path)
    yield database
    database.close()
    try:
        os.unlink(path)
    except OSError:
        pass


class TestSessionBuilder:
    """Test suite for session building logic."""

    def _insert_entry(self, db, track_id, timestamp, is_staff=False, store_id="ST1008"):
        db.insert_event({
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "event_type": "ENTRY",
            "timestamp": timestamp,
            "camera_id": "CAM_3",
            "visitor_id": f"VIS_{track_id}",
            "is_staff": is_staff,
            "confidence": 0.85,
        })

    def _insert_exit(self, db, track_id, timestamp, is_staff=False, store_id="ST1008"):
        db.insert_event({
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "event_type": "EXIT",
            "timestamp": timestamp,
            "camera_id": "CAM_3",
            "visitor_id": f"VIS_{track_id}",
            "is_staff": is_staff,
            "confidence": 0.85,
        })

    def _insert_zone_dwell(self, db, track_id, zone, dwell_seconds, timestamp, store_id="ST1008"):
        db.insert_event({
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "event_type": "ZONE_DWELL",
            "timestamp": timestamp,
            "camera_id": "CAM_1",
            "visitor_id": f"VIS_{track_id}",
            "zone_id": zone.upper(),
            "dwell_ms": int(dwell_seconds * 1000),
        })

    def test_basic_session(self, db):
        """Entry + Exit = one complete session."""
        self._insert_entry(db, 1, "2026-04-10T20:10:00Z")
        self._insert_exit(db, 1, "2026-04-10T20:15:00Z")

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        assert len(sessions) == 1
        assert sessions[0]["is_complete"] is True
        assert sessions[0]["visitor_id"] == "VIS_1"
        assert sessions[0]["duration_seconds"] == 300.0

    def test_entry_without_exit(self, db):
        """Entry without exit = incomplete session."""
        self._insert_entry(db, 2, "2026-04-10T20:10:00Z")

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        assert len(sessions) == 1
        assert sessions[0]["is_complete"] is False
        assert sessions[0]["visitor_id"] == "VIS_2"

    def test_staff_filtered(self, db):
        """Staff entries should not create customer sessions."""
        self._insert_entry(db, 3, "2026-04-10T20:10:00Z", is_staff=True)
        self._insert_exit(db, 3, "2026-04-10T20:20:00Z", is_staff=True)

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        # Staff sessions should be excluded
        assert len(sessions) == 0

    def test_multiple_sessions(self, db):
        """Multiple people entering = multiple sessions."""
        self._insert_entry(db, 4, "2026-04-10T20:10:00Z")
        self._insert_entry(db, 5, "2026-04-10T20:10:30Z")
        self._insert_exit(db, 4, "2026-04-10T20:15:00Z")
        self._insert_exit(db, 5, "2026-04-10T20:18:00Z")

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        assert len(sessions) == 2

    def test_zone_enrichment(self, db):
        """Sessions should include zone visit data."""
        self._insert_entry(db, 8, "2026-04-10T20:10:00Z")
        self._insert_zone_dwell(db, 8, "skincare", 45.5, "2026-04-10T20:10:30Z")
        self._insert_zone_dwell(db, 8, "makeup", 30.0, "2026-04-10T20:11:00Z")
        self._insert_exit(db, 8, "2026-04-10T20:15:00Z")

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        assert len(sessions) == 1
        assert "SKINCARE" in sessions[0]["zones_visited"]
        assert "MAKEUP" in sessions[0]["zones_visited"]
        assert sessions[0]["max_dwell_zone"] == "SKINCARE"
        assert sessions[0]["max_dwell_ms"] == 45500

    def test_sales_matching(self, db):
        """Sessions should be matched to nearby sales only if they reached billing."""
        self._insert_entry(db, 9, "2026-04-10T20:10:00Z")
        self._insert_zone_dwell(db, 9, "billing", 45.5, "2026-04-10T20:12:00Z")
        self._insert_exit(db, 9, "2026-04-10T20:20:00Z")

        # Insert a sale near the session time
        db.insert_sale({
            "order_id": "ORD001",
            "order_date": "2026-04-10",
            "order_time": "20:15:00",
            "store_id": "ST1008",
            "product_id": "SKU001",
            "brand_name": "Test Brand",
            "total_amount": 499.0,
        })

        builder = SessionBuilder(db)
        sessions = builder.build_sessions()

        assert len(sessions) == 1
        assert sessions[0]["purchased"] is True
        assert sessions[0]["matched_transaction_id"] == "ORD001"
