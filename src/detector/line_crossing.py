"""
Virtual line crossing detector for entry/exit counting.

Used on CAM 3 (entrance camera) to detect when a person crosses
the door threshold. Uses centroid tracking with hysteresis to
prevent flickering at the boundary.

Design Decision: Virtual line approach chosen over ROI-based
entry/exit because:
1. More precise direction detection (left→right vs right→left)
2. Handles partial occlusion better (only centroid needs to cross)
3. Simpler to calibrate (one x-coordinate vs. two ROI polygons)

The hysteresis buffer prevents rapid re-triggering when a person
stands near the line threshold.
"""
from collections import defaultdict
from typing import Optional

import structlog

from src.config import Config

logger = structlog.get_logger(__name__)


class LineCrossingDetector:
    """
    Detects when tracked persons cross a virtual horizontal line.

    For CAM 3 (entrance):
    - Line is at y=650 (configurable), roughly at the door threshold
    - TOP side = inside store (y < line_y)
    - BOTTOM side = outside store (y > line_y)
    - Entry: person moves from BOTTOM → TOP (outside → inside)
    - Exit: person moves from TOP → BOTTOM (inside → outside)

    Uses a hysteresis zone around the line to prevent flickering.
    """

    def __init__(
        self,
        line_y: Optional[int] = None,
        min_frames: Optional[int] = None,
        hysteresis: Optional[int] = None,
    ):
        self.line_y = line_y or Config.VIRTUAL_LINE_Y
        self.min_frames = min_frames or Config.CROSSING_MIN_FRAMES
        self.hysteresis = hysteresis or Config.CROSSING_HYSTERESIS

        # line boundaries with hysteresis
        self.line_top = self.line_y - self.hysteresis
        self.line_bottom = self.line_y + self.hysteresis

        # Track state per track_id
        # Each entry: {"positions": [(cy, frame_idx)], "side": "top"|"bottom"|"on_line", "crossings": [...]}
        self.tracks: dict[int, dict] = defaultdict(
            lambda: {"positions": [], "side": None, "crossings": []}
        )

        self.total_entries = 0
        self.total_exits = 0

        logger.info(
            "line_crossing.initialized",
            line_y=self.line_y,
            hysteresis=self.hysteresis,
            min_frames=self.min_frames,
        )

    def _get_side(self, cy: float) -> str:
        """Determine which side of the line a centroid is on."""
        if cy < self.line_top:
            return "top"  # inside store
        elif cy > self.line_bottom:
            return "bottom"  # outside store
        else:
            return "on_line"  # in the hysteresis zone

    def update(
        self, track_id: int, centroid_y: float, frame_idx: int
    ) -> Optional[str]:
        """
        Update a track with its new centroid position.

        Args:
            track_id: Unique track ID from ByteTrack
            centroid_y: Y coordinate of person's centroid
            frame_idx: Current frame number

        Returns:
            "entry" if person entered the store
            "exit" if person exited the store
            None if no crossing detected
        """
        track = self.tracks[track_id]
        track["positions"].append((centroid_y, frame_idx))

        current_side = self._get_side(centroid_y)

        # First observation: establish initial side
        if track["side"] is None:
            if current_side != "on_line":
                track["side"] = current_side
            return None

        # If on the line, don't update side (hysteresis)
        if current_side == "on_line":
            return None

        # Check for crossing
        previous_side = track["side"]

        if current_side != previous_side:
            # Verify this is sustained: check that we have enough frames
            # on the new side to confirm the crossing
            if len(track["positions"]) < self.min_frames:
                track["side"] = current_side
                return None

            # Confirm: the last min_frames positions should all be on the new side
            recent = track["positions"][-self.min_frames :]
            recent_sides = [self._get_side(pos[0]) for pos in recent]

            # Allow "on_line" in recent frames (person is transitioning)
            definitive_sides = [s for s in recent_sides if s != "on_line"]
            if not definitive_sides:
                return None

            # Majority should be on the new side
            new_side_count = sum(1 for s in definitive_sides if s == current_side)
            if new_side_count < len(definitive_sides) * 0.5:
                return None

            # Crossing confirmed!
            track["side"] = current_side

            if previous_side == "bottom" and current_side == "top":
                # Moved from outside (bottom) to inside (top) = ENTRY
                crossing_type = "entry"
                self.total_entries += 1
                track["crossings"].append(
                    {"type": crossing_type, "frame": frame_idx}
                )
                logger.info(
                    "line_crossing.entry_detected",
                    track_id=track_id,
                    frame=frame_idx,
                    total_entries=self.total_entries,
                )
                return crossing_type

            elif previous_side == "top" and current_side == "bottom":
                # Moved from inside (top) to outside (bottom) = EXIT
                crossing_type = "exit"
                self.total_exits += 1
                track["crossings"].append(
                    {"type": crossing_type, "frame": frame_idx}
                )
                logger.info(
                    "line_crossing.exit_detected",
                    track_id=track_id,
                    frame=frame_idx,
                    total_exits=self.total_exits,
                )
                return crossing_type

        return None

    def get_stats(self) -> dict:
        """Return current crossing statistics."""
        return {
            "total_entries": self.total_entries,
            "total_exits": self.total_exits,
            "active_tracks": len(self.tracks),
            "line_y": self.line_y,
        }

    def get_track_crossings(self, track_id: int) -> list[dict]:
        """Return all crossings for a specific track."""
        if track_id in self.tracks:
            return self.tracks[track_id]["crossings"]
        return []
