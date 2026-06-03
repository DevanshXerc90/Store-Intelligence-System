"""
SQLite database manager for the Store Intelligence System.

Handles schema creation, event storage, session management, and sales data.
Supports multi-store queries via store_id filtering.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

from src.config import Config

logger = structlog.get_logger(__name__)


class Database:
    """Thread-safe SQLite database wrapper with multi-store support."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path, timeout=30, check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        return self._local.conn

    @contextmanager
    def get_connection(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self):
        """Create all tables if they don't exist."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    store_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    visitor_id TEXT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    zone_id TEXT,
                    dwell_ms INTEGER,
                    is_staff INTEGER DEFAULT 0,
                    confidence REAL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_events_store ON events(store_id);
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_visitor ON events(visitor_id);
                CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone_id);

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    visitor_id TEXT,
                    store_id TEXT NOT NULL,
                    entry_time TEXT,
                    exit_time TEXT,
                    duration_seconds REAL,
                    is_staff INTEGER DEFAULT 0,
                    is_complete INTEGER DEFAULT 1,
                    is_reentry INTEGER DEFAULT 0,
                    zones_visited TEXT DEFAULT '[]',
                    zone_dwells TEXT DEFAULT '{}',
                    max_dwell_zone TEXT,
                    max_dwell_ms INTEGER,
                    reached_billing INTEGER DEFAULT 0,
                    purchased INTEGER DEFAULT 0,
                    matched_transaction_id TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_store ON sessions(store_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_entry ON sessions(entry_time);
                CREATE INDEX IF NOT EXISTS idx_sessions_staff ON sessions(is_staff);

                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    order_date TEXT,
                    order_time TEXT,
                    store_id TEXT,
                    product_id TEXT,
                    brand_name TEXT,
                    total_amount REAL
                );

                CREATE INDEX IF NOT EXISTS idx_sales_order ON sales(order_id);
                CREATE INDEX IF NOT EXISTS idx_sales_store ON sales(store_id);
                CREATE INDEX IF NOT EXISTS idx_sales_time ON sales(order_time);

                CREATE TABLE IF NOT EXISTS anomalies (
                    anomaly_id TEXT PRIMARY KEY,
                    store_id TEXT NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT,
                    suggested_action TEXT DEFAULT '',
                    timestamp TEXT,
                    details TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_anomalies_store ON anomalies(store_id);

                CREATE TABLE IF NOT EXISTS processing_status (
                    camera_id TEXT PRIMARY KEY,
                    store_id TEXT,
                    status TEXT DEFAULT 'pending',
                    frames_processed INTEGER DEFAULT 0,
                    total_frames INTEGER DEFAULT 0,
                    events_generated INTEGER DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT
                );
            """
            )
        logger.info("database.initialized", path=self.db_path)

    # ── Event Operations ───────────────────────────────────────────

    def insert_event(self, event: dict) -> bool:
        """
        Insert a single event. Returns True if inserted, False if duplicate.
        Uses INSERT OR IGNORE for idempotency by event_id.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO events
                (event_id, store_id, camera_id, visitor_id, event_type,
                 timestamp, zone_id, dwell_ms, is_staff, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.get("event_id"),
                    event.get("store_id", ""),
                    event.get("camera_id", ""),
                    event.get("visitor_id", ""),
                    event.get("event_type", ""),
                    event.get("timestamp", ""),
                    event.get("zone_id"),
                    event.get("dwell_ms"),
                    1 if event.get("is_staff") else 0,
                    event.get("confidence"),
                    json.dumps(event.get("metadata", {})),
                ),
            )
            return cursor.rowcount > 0

    def event_exists(self, event_id: str) -> bool:
        """Check if an event_id already exists (for dedup)."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return row is not None

    def get_events(
        self,
        store_id: Optional[str] = None,
        event_type: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.upper())
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_event_count(
        self,
        store_id: Optional[str] = None,
        event_type: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> int:
        query = "SELECT COUNT(*) as cnt FROM events WHERE 1=1"
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.upper())
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchone()["cnt"]

    def get_entry_exit_counts(self, store_id: Optional[str] = None) -> dict:
        with self.get_connection() as conn:
            store_filter = ""
            params: list[Any] = []
            if store_id:
                store_filter = " AND store_id = ?"
                params = [store_id]

            entries = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='ENTRY' AND is_staff=0{store_filter}",
                params,
            ).fetchone()["cnt"]
            exits = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='EXIT' AND is_staff=0{store_filter}",
                params,
            ).fetchone()["cnt"]
            staff_entries = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='ENTRY' AND is_staff=1{store_filter}",
                params,
            ).fetchone()["cnt"]
            reentries = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='REENTRY' AND is_staff=0{store_filter}",
                params,
            ).fetchone()["cnt"]
            return {
                "entries": entries,
                "exits": exits,
                "staff_entries": staff_entries,
                "reentries": reentries,
            }

    def get_unique_visitors(self, store_id: Optional[str] = None) -> int:
        """Count unique visitor_ids for non-staff ENTRY events."""
        query = "SELECT COUNT(DISTINCT visitor_id) as cnt FROM events WHERE event_type='ENTRY' AND is_staff=0"
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchone()["cnt"]

    def get_zone_dwell_stats(self, store_id: Optional[str] = None) -> list[dict]:
        """Get avg dwell per zone for non-staff events."""
        query = """
            SELECT zone_id,
                   AVG(dwell_ms) as avg_dwell_ms,
                   COUNT(*) as visit_count
            FROM events
            WHERE event_type = 'ZONE_DWELL' AND is_staff = 0 AND zone_id IS NOT NULL
        """
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        query += " GROUP BY zone_id ORDER BY visit_count DESC"
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_zone_visit_counts(self, store_id: Optional[str] = None) -> list[dict]:
        """Get zone visit frequency (ZONE_ENTER events) for heatmap."""
        query = """
            SELECT zone_id,
                   COUNT(*) as visit_count,
                   AVG(COALESCE(dwell_ms, 0)) as avg_dwell_ms
            FROM events
            WHERE event_type IN ('ZONE_ENTER', 'ZONE_DWELL') AND is_staff = 0 AND zone_id IS NOT NULL
        """
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        query += " GROUP BY zone_id ORDER BY visit_count DESC"
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_queue_stats(self, store_id: Optional[str] = None) -> dict:
        """Get billing queue statistics."""
        store_filter = ""
        params: list[Any] = []
        if store_id:
            store_filter = " AND store_id = ?"
            params = [store_id]

        with self.get_connection() as conn:
            joins = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='BILLING_QUEUE_JOIN'{store_filter}",
                params,
            ).fetchone()["cnt"]
            abandons = conn.execute(
                f"SELECT COUNT(*) as cnt FROM events WHERE event_type='BILLING_QUEUE_ABANDON'{store_filter}",
                params,
            ).fetchone()["cnt"]

            # Latest queue depth from metadata
            latest_queue = conn.execute(
                f"""SELECT metadata FROM events
                    WHERE event_type='BILLING_QUEUE_JOIN'{store_filter}
                    ORDER BY timestamp DESC LIMIT 1""",
                params,
            ).fetchone()
            queue_depth = None
            if latest_queue:
                try:
                    meta = json.loads(latest_queue["metadata"])
                    queue_depth = meta.get("queue_depth")
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "queue_joins": joins,
                "queue_abandons": abandons,
                "abandonment_rate": round(abandons / joins, 4) if joins > 0 else 0.0,
                "current_queue_depth": queue_depth,
            }

    def get_last_event_timestamp(self, store_id: Optional[str] = None) -> Optional[str]:
        """Get the most recent event timestamp for a store."""
        query = "SELECT MAX(timestamp) as ts FROM events"
        params: list[Any] = []
        if store_id:
            query += " WHERE store_id = ?"
            params.append(store_id)
        with self.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return row["ts"] if row else None

    def get_all_store_ids(self) -> list[str]:
        """Get all distinct store_ids from events."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT store_id FROM events WHERE store_id != '' ORDER BY store_id"
            ).fetchall()
            return [r["store_id"] for r in rows]

    # ── Session Operations ─────────────────────────────────────────

    def insert_session(self, session: dict) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, visitor_id, store_id, entry_time, exit_time,
                 duration_seconds, is_staff, is_complete, is_reentry,
                 zones_visited, zone_dwells, max_dwell_zone, max_dwell_ms,
                 reached_billing, purchased, matched_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session.get("session_id"),
                    session.get("visitor_id"),
                    session.get("store_id", ""),
                    session.get("entry_time"),
                    session.get("exit_time"),
                    session.get("duration_seconds"),
                    1 if session.get("is_staff") else 0,
                    1 if session.get("is_complete", True) else 0,
                    1 if session.get("is_reentry") else 0,
                    json.dumps(session.get("zones_visited", [])),
                    json.dumps(session.get("zone_dwells", {})),
                    session.get("max_dwell_zone"),
                    session.get("max_dwell_ms"),
                    1 if session.get("reached_billing") else 0,
                    1 if session.get("purchased") else 0,
                    session.get("matched_transaction_id"),
                ),
            )

    def get_sessions(
        self, store_id: Optional[str] = None, include_staff: bool = False
    ) -> list[dict]:
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        if not include_staff:
            query += " AND is_staff=0"
        query += " ORDER BY entry_time ASC"
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["zones_visited"] = json.loads(d.get("zones_visited", "[]"))
                d["zone_dwells"] = json.loads(d.get("zone_dwells", "{}"))
                result.append(d)
            return result

    def get_session_count(
        self, store_id: Optional[str] = None, include_staff: bool = False
    ) -> int:
        query = "SELECT COUNT(*) as cnt FROM sessions WHERE 1=1"
        params: list[Any] = []
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        if not include_staff:
            query += " AND is_staff=0"
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchone()["cnt"]

    def get_funnel_counts(self, store_id: Optional[str] = None) -> dict:
        """
        Get funnel stage counts from sessions:
        Entry → Zone Visit → Billing Queue → Purchase
        """
        store_filter = ""
        params: list[Any] = []
        if store_id:
            store_filter = " AND store_id = ?"
            params = [store_id]

        with self.get_connection() as conn:
            # Entry: unique visitors (non-staff, non-reentry sessions)
            entries = conn.execute(
                f"""SELECT COUNT(DISTINCT visitor_id) as cnt FROM sessions
                    WHERE is_staff=0{store_filter}""",
                params,
            ).fetchone()["cnt"]

            # Zone Visit: visitors who visited at least one zone
            zone_visits = conn.execute(
                f"""SELECT COUNT(DISTINCT visitor_id) as cnt FROM sessions
                    WHERE is_staff=0 AND zones_visited != '[]'{store_filter}""",
                params,
            ).fetchone()["cnt"]

            # Billing Queue: visitors who reached billing
            billing = conn.execute(
                f"""SELECT COUNT(DISTINCT visitor_id) as cnt FROM sessions
                    WHERE is_staff=0 AND reached_billing=1{store_filter}""",
                params,
            ).fetchone()["cnt"]

            # Purchase: visitors who purchased
            purchased = conn.execute(
                f"""SELECT COUNT(DISTINCT visitor_id) as cnt FROM sessions
                    WHERE is_staff=0 AND purchased=1{store_filter}""",
                params,
            ).fetchone()["cnt"]

            return {
                "entry": entries,
                "zone_visit": zone_visits,
                "billing_queue": billing,
                "purchase": purchased,
            }

    # ── Sales Operations ───────────────────────────────────────────

    def insert_sale(self, sale: dict) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sales
                (order_id, order_date, order_time, store_id,
                 product_id, brand_name, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    sale.get("order_id"),
                    sale.get("order_date"),
                    sale.get("order_time"),
                    sale.get("store_id"),
                    sale.get("product_id"),
                    sale.get("brand_name"),
                    sale.get("total_amount"),
                ),
            )

    def get_sales_summary(self, store_id: Optional[str] = None) -> dict:
        store_filter = ""
        params: list[Any] = []
        if store_id:
            store_filter = " WHERE store_id = ?"
            params = [store_id]

        with self.get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM sales{store_filter}", params
            ).fetchone()["cnt"]
            if total == 0:
                return {
                    "total_line_items": 0,
                    "unique_orders": 0,
                    "total_revenue": 0.0,
                    "avg_order_value": 0.0,
                }

            and_filter = store_filter.replace("WHERE", "AND") if store_filter else ""

            unique_orders = conn.execute(
                f"SELECT COUNT(DISTINCT order_id) as cnt FROM sales{store_filter}",
                params,
            ).fetchone()["cnt"]

            total_revenue = conn.execute(
                f"SELECT COALESCE(SUM(total_amount), 0) as total FROM sales{store_filter}",
                params,
            ).fetchone()["total"]

            # Per-order revenue for average
            order_rev = conn.execute(
                f"SELECT SUM(total_amount) as order_total FROM sales{store_filter} GROUP BY order_id",
                params,
            ).fetchall()
            avg_ov = (
                sum(r["order_total"] for r in order_rev) / len(order_rev)
                if order_rev
                else 0
            )

            return {
                "total_line_items": total,
                "unique_orders": unique_orders,
                "total_revenue": round(total_revenue, 2),
                "avg_order_value": round(avg_ov, 2),
            }

    def get_sales_in_window(
        self, store_id: str, start_time: str, end_time: str
    ) -> list[dict]:
        """Get sales within a time window for POS correlation."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM sales
                   WHERE store_id = ? AND order_time >= ? AND order_time <= ?
                   ORDER BY order_time""",
                (store_id, start_time, end_time),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_hourly_sales(self, store_id: Optional[str] = None) -> list[dict]:
        store_filter = ""
        params: list[Any] = []
        if store_id:
            store_filter = " WHERE store_id = ?"
            params = [store_id]
        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    SUBSTR(order_time, 1, 2) as hour,
                    COUNT(DISTINCT order_id) as orders,
                    COALESCE(SUM(total_amount), 0) as revenue
                FROM sales{store_filter}
                GROUP BY SUBSTR(order_time, 1, 2)
                ORDER BY hour
            """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Anomaly Operations ─────────────────────────────────────────

    def insert_anomaly(self, anomaly: dict) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO anomalies
                (anomaly_id, store_id, anomaly_type, severity,
                 description, suggested_action, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    anomaly.get("anomaly_id"),
                    anomaly.get("store_id", ""),
                    anomaly.get("anomaly_type"),
                    anomaly.get("severity"),
                    anomaly.get("description"),
                    anomaly.get("suggested_action", ""),
                    anomaly.get("timestamp"),
                    json.dumps(anomaly.get("details", {})),
                ),
            )

    def get_anomalies(self, store_id: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM anomalies"
        params: list[Any] = []
        if store_id:
            query += " WHERE store_id = ?"
            params.append(store_id)
        query += " ORDER BY created_at DESC"
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["details"] = json.loads(d.get("details", "{}"))
                result.append(d)
            return result

    # ── Processing Status ──────────────────────────────────────────

    def update_processing_status(
        self, camera_id: str, status: str, store_id: str = "", **kwargs
    ) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processing_status (camera_id, store_id, status)
                VALUES (?, ?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET status=excluded.status, store_id=excluded.store_id
            """,
                (camera_id, store_id, status),
            )
            for key, value in kwargs.items():
                if key in (
                    "frames_processed",
                    "total_frames",
                    "events_generated",
                    "started_at",
                    "completed_at",
                ):
                    conn.execute(
                        f"UPDATE processing_status SET {key}=? WHERE camera_id=?",
                        (value, camera_id),
                    )

    def get_processing_status(self) -> list[dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM processing_status").fetchall()
            return [dict(r) for r in rows]

    def is_processing_complete(self) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done
                FROM processing_status
            """
            ).fetchone()
            return row["total"] > 0 and row["total"] == row["done"]

    def get_total_events(self) -> int:
        with self.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()["cnt"]

    def deduplicate_events(self) -> int:
        """
        Remove duplicate events based on (store_id, camera_id, visitor_id, event_type, timestamp).
        Returns the number of removed duplicates.
        """
        with self.get_connection() as conn:
            dupes = conn.execute(
                """
                DELETE FROM events
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM events
                    GROUP BY event_type, store_id, camera_id, visitor_id,
                             COALESCE(zone_id, ''),
                             COALESCE(dwell_ms, -1),
                             timestamp
                )
            """
            )
            removed = dupes.rowcount
            if removed > 0:
                logger.info("database.deduplicated", removed=removed)
            return removed

    def reset_for_reprocessing(self) -> None:
        """
        Clear all events, sessions, anomalies, and processing status.
        Sales data is also cleared since it's reloaded from CSV on each startup.
        """
        with self.get_connection() as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM anomalies")
            conn.execute("DELETE FROM processing_status")
            conn.execute("DELETE FROM sales")
        logger.info("database.reset_for_reprocessing")

    def close(self) -> None:
        """Close the database connection (needed for clean teardown on Windows)."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
