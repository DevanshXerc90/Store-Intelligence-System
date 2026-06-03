"""
Anomaly detection for store intelligence.

Identifies operational issues combining CCTV events with sales data:
- BILLING_QUEUE_SPIKE: Queue length exceeds limits (requires checkout support)
- CONVERSION_DROP: Conversion rate drops below target (bottlenecks)
- DEAD_ZONE: Product zone receives zero traffic for >30 minutes (appealing layout check)
- UNUSUAL_TRAFFIC: Activity patterns that deviate from normal (staffing adjustment)
"""
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.config import Config
from src.database import Database

logger = structlog.get_logger("anomaly_detector")


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse ISO-8601 format timestamp string."""
    if not ts:
        return None
    try:
        clean_ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_ts)
    except (ValueError, TypeError):
        return None


class AnomalyDetector:
    """
    Retail anomaly detection system running on top of sessions and events.
    """

    def __init__(self, db: Database):
        self.db = db

    def run_detection(self) -> list[dict]:
        """Run all anomaly detection checks across all stores and store results."""
        logger.info("anomaly_detector.starting")

        anomalies = []
        store_ids = self.db.get_all_store_ids()

        for store_id in store_ids:
            logger.info("anomaly_detector.processing_store", store_id=store_id)
            
            # Run checks for this specific store
            anomalies.extend(self._check_queue_spikes(store_id))
            anomalies.extend(self._check_conversion_drop(store_id))
            anomalies.extend(self._check_dead_zones(store_id))
            anomalies.extend(self._check_unusual_traffic(store_id))

        # Store anomalies in database
        for anomaly in anomalies:
            self.db.insert_anomaly(anomaly)

        logger.info("anomaly_detector.complete", total_anomalies=len(anomalies))
        return anomalies

    def _check_queue_spikes(self, store_id: str) -> list[dict]:
        """Flag queue spikes when queue depth is above threshold."""
        anomalies = []
        
        # Query queue events
        events = self.db.get_events(store_id=store_id, event_type="BILLING_QUEUE_JOIN", limit=1000)
        
        for e in events:
            meta = {}
            try:
                meta = json.loads(e.get("metadata", "{}")) if isinstance(e.get("metadata"), str) else e.get("metadata", {})
            except Exception:
                pass
            
            queue_depth = meta.get("queue_depth")
            if queue_depth and queue_depth >= Config.ANOMALY_QUEUE_SPIKE_THRESHOLD:
                severity = "CRITICAL" if queue_depth >= 8 else "WARN"
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "store_id": store_id,
                    "anomaly_type": "BILLING_QUEUE_SPIKE",
                    "severity": severity,
                    "description": f"Billing counter queue spike: current queue depth is {queue_depth}.",
                    "suggested_action": "Open additional billing counters immediately to handle checkouts.",
                    "timestamp": e.get("timestamp"),
                    "details": {
                        "queue_depth": queue_depth,
                        "threshold": Config.ANOMALY_QUEUE_SPIKE_THRESHOLD,
                        "camera_id": e.get("camera_id"),
                    }
                })
        return anomalies

    def _check_conversion_drop(self, store_id: str) -> list[dict]:
        """Flag if conversion rate falls below baseline target."""
        anomalies = []
        
        # Calculate conversion rate
        unique_visitors = self.db.get_unique_visitors(store_id)
        sessions = self.db.get_sessions(store_id=store_id, include_staff=False)
        purchased_count = sum(1 for s in sessions if s.get("purchased"))
        
        if unique_visitors >= 5:  # Require some traffic to avoid noise
            conversion_rate = purchased_count / unique_visitors
            
            # Flag if conversion rate is under 15% (baseline target)
            target = 0.15
            if conversion_rate < target:
                severity = "CRITICAL" if conversion_rate < 0.05 else "WARN"
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "store_id": store_id,
                    "anomaly_type": "CONVERSION_DROP",
                    "severity": severity,
                    "description": f"Store conversion rate dropped to {conversion_rate:.1%} (target: {target:.1%}).",
                    "suggested_action": "Inspect checkout queue times, billing speed, and floor sales assistance.",
                    "timestamp": datetime.now().isoformat() + "Z",
                    "details": {
                        "conversion_rate": conversion_rate,
                        "target": target,
                        "unique_visitors": unique_visitors,
                        "purchased_count": purchased_count,
                    }
                })
        return anomalies

    def _check_dead_zones(self, store_id: str) -> list[dict]:
        """Flag dead zones receiving zero visits for over 30 minutes."""
        anomalies = []
        
        # Get all distinct zones and their last event timestamps
        events = self.db.get_events(store_id=store_id, limit=50000)
        if not events:
            return anomalies

        # Find the overall latest event time as current store time
        latest_ts = None
        for e in events:
            dt = parse_timestamp(e.get("timestamp", ""))
            if dt and (not latest_ts or dt > latest_ts):
                latest_ts = dt

        if not latest_ts:
            return anomalies

        # Group latest timestamp by zone_id
        zone_last_seen = {}
        for e in events:
            zone_id = e.get("zone_id") or e.get("zone")
            if zone_id:
                zone_upper = zone_id.upper()
                if zone_upper not in ("ENTRANCE", "EXIT"):
                    dt = parse_timestamp(e.get("timestamp", ""))
                    if dt:
                        if zone_upper not in zone_last_seen or dt > zone_last_seen[zone_upper]:
                            zone_last_seen[zone_upper] = dt

        # Flag any zone not visited for 30 minutes
        for zone_id, last_seen_dt in zone_last_seen.items():
            elapsed_minutes = (latest_ts - last_seen_dt).total_seconds() / 60
            if elapsed_minutes >= Config.ANOMALY_DEAD_ZONE_MINUTES:
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "store_id": store_id,
                    "anomaly_type": "DEAD_ZONE",
                    "severity": "INFO",
                    "description": f"Zero visitor activity detected in zone {zone_id} for the last {int(elapsed_minutes)} minutes.",
                    "suggested_action": "Verify if displays are organized, products are stocked, or lighting is functional.",
                    "timestamp": latest_ts.isoformat() + "Z",
                    "details": {
                        "zone_id": zone_id,
                        "inactive_minutes": round(elapsed_minutes, 1),
                        "last_activity_time": last_seen_dt.isoformat() + "Z",
                    }
                })

        return anomalies

    def _check_unusual_traffic(self, store_id: str) -> list[dict]:
        """Detect and flag off-hour activity or statistical visitor surges."""
        anomalies = []
        events = self.db.get_events(store_id=store_id, limit=10000)
        
        for e in events:
            et = e.get("event_type", "").upper()
            if et == "ENTRY":
                ts = e.get("timestamp", "")
                dt = parse_timestamp(ts)
                if dt:
                    # Business hours are 10:00 to 22:00
                    if dt.hour < 10 or dt.hour >= 22:
                        anomalies.append({
                            "anomaly_id": str(uuid.uuid4()),
                            "store_id": store_id,
                            "anomaly_type": "UNUSUAL_TRAFFIC",
                            "severity": "CRITICAL",
                            "description": f"Customer entry detected at {dt.strftime('%H:%M:%S')} (outside business hours 10AM-10PM).",
                            "suggested_action": "Verify security log and check store lock status.",
                            "timestamp": ts,
                            "details": {
                                "hour": dt.hour,
                                "event_type": "ENTRY",
                                "camera_id": e.get("camera_id"),
                            }
                        })
        return anomalies
import json
