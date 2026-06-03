"""
Session builder — groups entry/exit and zone events into customer visit sessions.

Scoped by store_id and visitor_id to handle multi-store deployments.
Implements the temporal POS transaction correlation rule:
- A visitor who was in the billing zone in the 5-minute window before a transaction
  counts as a converted visitor.
"""
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.config import Config
from src.database import Database

logger = structlog.get_logger("session_builder")


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse ISO-8601 format timestamp string."""
    if not ts:
        return None
    try:
        # Strip trailing Z and replace with UTC offset for parsing compatibility
        clean_ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_ts)
    except (ValueError, TypeError):
        return None


class SessionBuilder:
    """
    Builds customer sessions from event-level data and correlates with POS.
    """

    def __init__(self, db: Database):
        self.db = db

    def build_sessions(self) -> list[dict]:
        """
        Build all sessions from stored events across all stores.
        """
        logger.info("session_builder.starting")

        # Get all distinct store IDs
        store_ids = self.db.get_all_store_ids()
        all_built_sessions = []

        for store_id in store_ids:
            logger.info("session_builder.processing_store", store_id=store_id)
            
            # Fetch all events for this store
            events = self.db.get_events(store_id=store_id, limit=50000)
            if not events:
                continue

            # Group events by visitor_id
            events_by_visitor = defaultdict(list)
            for e in events:
                v_id = e.get("visitor_id") or f"VIS_{e.get('track_id')}"
                if v_id and v_id != "VIS_None":
                    events_by_visitor[v_id].append(e)

            # Retrieve sales for this store
            sales_summary = self.db.get_sales_in_window(store_id, "00:00:00", "23:59:59")
            matched_sales = set()

            for visitor_id, v_events in events_by_visitor.items():
                # Separate staff events
                is_staff = any(bool(e.get("is_staff")) for e in v_events)
                if is_staff:
                    continue  # We only build funnel sessions for customers

                # Sort visitor events chronologically
                v_events.sort(key=lambda x: x.get("timestamp", ""))

                entry_time_dt = None
                exit_time_dt = None
                is_complete = False
                is_reentry = False
                reached_billing = False
                billing_time_dt = None

                zones_visited = set()
                zone_dwells = defaultdict(int)  # zone_id -> total dwell_ms

                for e in v_events:
                    et = e.get("event_type", "").upper()
                    ts = e.get("timestamp")
                    ts_dt = parse_timestamp(ts)

                    # Mark entry/exit times
                    if et == "ENTRY":
                        if not entry_time_dt or (ts_dt and ts_dt < entry_time_dt):
                            entry_time_dt = ts_dt
                    elif et == "EXIT":
                        if not exit_time_dt or (ts_dt and ts_dt > exit_time_dt):
                            exit_time_dt = ts_dt
                            is_complete = True
                    elif et == "REENTRY":
                        is_reentry = True
                        if not entry_time_dt or (ts_dt and ts_dt < entry_time_dt):
                            entry_time_dt = ts_dt

                    # Track zones visited & dwell times
                    zone_id = e.get("zone_id") or e.get("zone")
                    if zone_id:
                        zone_upper = zone_id.upper()
                        if zone_upper not in ("ENTRANCE", "EXIT"):
                            zones_visited.add(zone_upper)
                            
                            # Check if billing zone
                            if "BILLING" in zone_upper:
                                reached_billing = True
                                if not billing_time_dt or (ts_dt and ts_dt < billing_time_dt):
                                    billing_time_dt = ts_dt

                            # Accumulate dwell milliseconds
                            dwell_ms = e.get("dwell_ms")
                            if dwell_ms is None and e.get("dwell_seconds") is not None:
                                dwell_ms = int(float(e["dwell_seconds"]) * 1000)
                            
                            if dwell_ms:
                                zone_dwells[zone_upper] += int(dwell_ms)

                # Fallbacks for entry/exit times
                if not entry_time_dt and v_events:
                    entry_time_dt = parse_timestamp(v_events[0].get("timestamp", ""))
                if not exit_time_dt and is_complete and v_events:
                    exit_time_dt = parse_timestamp(v_events[-1].get("timestamp", ""))

                duration_seconds = None
                if entry_time_dt and exit_time_dt:
                    duration_seconds = (exit_time_dt - entry_time_dt).total_seconds()
                elif entry_time_dt and reached_billing and billing_time_dt:
                    # Estimate duration up to billing zone entry
                    duration_seconds = (billing_time_dt - entry_time_dt).total_seconds()

                # Determine max dwell zone
                max_dwell_zone = None
                max_dwell_ms = None
                if zone_dwells:
                    max_dwell_zone = max(zone_dwells, key=zone_dwells.get)
                    max_dwell_ms = zone_dwells[max_dwell_zone]

                # Match POS transaction using the 5-minute pre-billing window rule
                purchased = False
                matched_txn_id = None

                if reached_billing and billing_time_dt and sales_summary:
                    # Convert billing_time_dt to HMS string for matching
                    # The visitor must be in the billing zone *before* the transaction
                    # So billing_time <= txn_time <= billing_time + 5 minutes
                    lower_limit = billing_time_dt
                    upper_limit = billing_time_dt + timedelta(seconds=Config.POS_CORRELATION_WINDOW_SECONDS)

                    best_match_txn = None
                    best_match_time = None

                    for sale in sales_summary:
                        txn_id = sale.get("order_id")
                        if txn_id in matched_sales:
                            continue

                        # Parse sale time (assume same date as billing event)
                        sale_time_str = sale.get("order_time", "")
                        try:
                            # Parse HMS order time
                            hms = datetime.strptime(sale_time_str, "%H:%M:%S").time()
                            sale_dt = datetime.combine(billing_time_dt.date(), hms).replace(tzinfo=billing_time_dt.tzinfo)
                            
                            if lower_limit <= sale_dt <= upper_limit:
                                if not best_match_time or sale_dt < best_match_time:
                                    best_match_time = sale_dt
                                    best_match_txn = txn_id
                        except Exception:
                            continue

                    if best_match_txn:
                        purchased = True
                        matched_txn_id = best_match_txn
                        matched_sales.add(best_match_txn)

                session_dict = {
                    "session_id": str(uuid.uuid4()),
                    "visitor_id": visitor_id,
                    "store_id": store_id,
                    "entry_time": entry_time_dt.isoformat() if entry_time_dt else None,
                    "exit_time": exit_time_dt.isoformat() if exit_time_dt else None,
                    "duration_seconds": round(duration_seconds, 2) if duration_seconds else None,
                    "is_staff": False,
                    "is_complete": is_complete,
                    "is_reentry": is_reentry,
                    "zones_visited": list(zones_visited),
                    "zone_dwells": dict(zone_dwells),
                    "max_dwell_zone": max_dwell_zone,
                    "max_dwell_ms": max_dwell_ms,
                    "reached_billing": reached_billing,
                    "purchased": purchased,
                    "matched_transaction_id": matched_txn_id,
                }

                self.db.insert_session(session_dict)
                all_built_sessions.append(session_dict)

        logger.info("session_builder.complete", total_sessions=len(all_built_sessions))
        return all_built_sessions
