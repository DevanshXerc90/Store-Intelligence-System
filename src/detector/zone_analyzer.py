"""
Zone dwell time analyzer for interior cameras.

Tracks how long each person spends in different store zones
(skincare, makeup, billing). Used to compute engagement metrics
and funnel progression.

Each camera covers a specific zone. The entire camera frame
is treated as the zone since each camera is dedicated to one area.
"""
from collections import defaultdict
from typing import Optional

import structlog

from src.config import Config

logger = structlog.get_logger(__name__)


class ZoneAnalyzer:
    """
    Tracks dwell time per person per zone (camera).

    Since each interior camera covers a distinct zone, we treat
    the entire camera frame as the zone boundary. A person is
    "in the zone" whenever they are detected in that camera's frames.

    Dwell time = (last_seen_frame - first_seen_frame) / fps
    """

    def __init__(self, camera_id: str, zone_name: str, fps: float):
        self.camera_id = camera_id
        self.zone_name = zone_name
        self.fps = fps

        # track_id → {"first_frame": int, "last_frame": int, "frame_count": int}
        self.track_presence: dict[int, dict] = defaultdict(
            lambda: {"first_frame": -1, "last_frame": -1, "frame_count": 0}
        )

        logger.info(
            "zone_analyzer.initialized",
            camera=camera_id,
            zone=zone_name,
            fps=fps,
        )

    def update(self, track_id: int, frame_idx: int) -> None:
        """Record that a track was seen in this zone at the given frame."""
        presence = self.track_presence[track_id]
        if presence["first_frame"] < 0:
            presence["first_frame"] = frame_idx
        presence["last_frame"] = frame_idx
        presence["frame_count"] += 1

    def get_dwell_times(self) -> list[dict]:
        """
        Compute dwell times for all tracks.

        Returns list of:
        {
            "track_id": int,
            "zone": str,
            "dwell_seconds": float,
            "first_frame": int,
            "last_frame": int,
            "frame_count": int
        }
        """
        results = []
        for track_id, presence in self.track_presence.items():
            if presence["first_frame"] < 0:
                continue

            # Dwell time based on frame range
            frame_range = presence["last_frame"] - presence["first_frame"]
            dwell_seconds = frame_range / self.fps if self.fps > 0 else 0

            # Only include if above minimum dwell threshold
            if dwell_seconds >= Config.MIN_DWELL_SECONDS:
                results.append(
                    {
                        "track_id": track_id,
                        "zone": self.zone_name,
                        "camera_id": self.camera_id,
                        "dwell_seconds": round(dwell_seconds, 2),
                        "first_frame": presence["first_frame"],
                        "last_frame": presence["last_frame"],
                        "frame_count": presence["frame_count"],
                    }
                )

        return results

    def get_track_dwell(self, track_id: int) -> Optional[float]:
        """Get dwell time for a specific track (seconds)."""
        if track_id not in self.track_presence:
            return None
        presence = self.track_presence[track_id]
        if presence["first_frame"] < 0:
            return None
        frame_range = presence["last_frame"] - presence["first_frame"]
        return round(frame_range / self.fps, 2) if self.fps > 0 else 0

    def identify_likely_staff(self, total_frames: int) -> set[int]:
        """
        Identify track IDs that are likely staff members.

        Heuristic: if a person is detected in more than
        STAFF_PRESENCE_THRESHOLD of total frames, they are
        likely a staff member (stationary, always present).
        """
        threshold = total_frames * Config.STAFF_PRESENCE_THRESHOLD
        staff_ids = set()
        for track_id, presence in self.track_presence.items():
            if presence["frame_count"] >= threshold:
                staff_ids.add(track_id)
                logger.info(
                    "zone_analyzer.staff_detected",
                    track_id=track_id,
                    zone=self.zone_name,
                    frame_count=presence["frame_count"],
                    threshold=threshold,
                )
        return staff_ids
