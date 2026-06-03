"""
Centralized configuration for the Store Intelligence System.
All settings can be overridden via environment variables.

Updated for multi-store support — no more hardcoded single store.
"""
import os
from pathlib import Path


class Config:
    """Application-wide configuration."""

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_EVENTS_STREAM: str = "store:events"
    REDIS_STATUS_KEY: str = "store:detector:status"
    REDIS_CONSUMER_GROUP: str = "api-consumers"
    REDIS_CONSUMER_NAME: str = "api-worker-1"

    # ── Database ───────────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", str(Path("data/db/store.db")))

    # ── Video Processing ───────────────────────────────────────────
    VIDEO_DIR: str = os.getenv("VIDEO_DIR", str(Path("data/videos")))
    TARGET_FPS: int = int(os.getenv("TARGET_FPS", "5"))
    YOLO_MODEL: str = os.getenv("YOLO_MODEL", "yolov8n.pt")
    PERSON_CLASS_ID: int = 0  # COCO class 0 = person
    PERSON_CONFIDENCE: float = float(os.getenv("PERSON_CONFIDENCE", "0.35"))
    MIN_BBOX_AREA: int = int(os.getenv("MIN_BBOX_AREA", "2000"))

    # ── Store Layout ──────────────────────────────────────────────
    STORE_LAYOUT_PATH: str = os.getenv(
        "STORE_LAYOUT_PATH", str(Path("data/store_layout.json"))
    )

    # ── Line Crossing (Entry cameras) ─────────────────────────────
    VIRTUAL_LINE_Y: int = int(os.getenv("VIRTUAL_LINE_Y", "650"))
    CROSSING_MIN_FRAMES: int = int(os.getenv("CROSSING_MIN_FRAMES", "3"))
    CROSSING_HYSTERESIS: int = int(os.getenv("CROSSING_HYSTERESIS", "30"))

    # ── Zone Analysis ──────────────────────────────────────────────
    MIN_DWELL_SECONDS: float = float(os.getenv("MIN_DWELL_SECONDS", "2.0"))
    DWELL_EMIT_INTERVAL_SECONDS: int = int(
        os.getenv("DWELL_EMIT_INTERVAL_SECONDS", "30")
    )

    # ── Staff Filtering ────────────────────────────────────────────
    STAFF_PRESENCE_THRESHOLD: float = float(
        os.getenv("STAFF_PRESENCE_THRESHOLD", "0.6")
    )

    # ── Session Builder ────────────────────────────────────────────
    REENTRY_WINDOW_SECONDS: int = int(os.getenv("REENTRY_WINDOW", "300"))
    SESSION_TIMEOUT_SECONDS: int = int(os.getenv("SESSION_TIMEOUT", "1800"))
    GROUP_ENTRY_WINDOW_SECONDS: int = int(os.getenv("GROUP_ENTRY_WINDOW", "3"))

    # ── POS Conversion Correlation ─────────────────────────────────
    # A visitor in the billing zone within this window before a POS
    # transaction counts as a converted visitor.
    POS_CORRELATION_WINDOW_SECONDS: int = int(
        os.getenv("POS_CORRELATION_WINDOW", "300")
    )  # 5 minutes

    # ── Sales Data ─────────────────────────────────────────────────
    SALES_CSV: str = os.getenv("SALES_CSV", str(Path("data/sales/pos_transactions.csv")))

    # ── API ─────────────────────────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # ── Anomaly Detection ──────────────────────────────────────────
    ANOMALY_ZSCORE_THRESHOLD: float = float(
        os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.0")
    )
    ANOMALY_QUEUE_SPIKE_THRESHOLD: int = int(
        os.getenv("ANOMALY_QUEUE_SPIKE_THRESHOLD", "5")
    )
    ANOMALY_DEAD_ZONE_MINUTES: int = int(
        os.getenv("ANOMALY_DEAD_ZONE_MINUTES", "30")
    )
    ANOMALY_STALE_FEED_MINUTES: int = int(
        os.getenv("ANOMALY_STALE_FEED_MINUTES", "10")
    )
