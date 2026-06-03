"""
Main detector orchestrator.

Processes all CCTV video files recursively, runs person detection + tracking,
and publishes structured events to Redis Streams.

This is the entry point for the detector service container.
"""
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import redis
import structlog

from src.config import Config
from src.detector.line_crossing import LineCrossingDetector
from src.detector.tracker import PersonTracker
from src.detector.zone_analyzer import ZoneAnalyzer

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger("detector")


def get_video_timestamp(frame, fps: float, frame_idx: int) -> str:
    """
    Extract timestamp from video frame overlay or compute from frame index.
    
    The CCTV footage has timestamps burned into the top-right corner.
    We compute timestamps from the video's known start time + frame offset.
    """
    # Base timestamp from the footage (around 20:09-20:10 on 10/04/2026)
    base_time = datetime(2026, 4, 10, 20, 9, 0)
    offset_seconds = frame_idx / fps if fps > 0 else 0
    ts = base_time.timestamp() + offset_seconds
    return datetime.fromtimestamp(ts).isoformat() + "Z"


def publish_event(r: redis.Redis, event: dict) -> None:
    """Publish an event to Redis Streams."""
    try:
        # Ensure all values are strings for Redis
        clean = {k: str(v) if v is not None else "" for k, v in event.items()}
        r.xadd(Config.REDIS_EVENTS_STREAM, clean, maxlen=50000)
    except Exception as e:
        logger.error("redis.publish_failed", error=str(e))


def map_camera_config(store_id: str, filename: str) -> dict:
    """
    Dynamically map a video file to its camera role and zone name.
    """
    fn = filename.lower()
    store_upper = store_id.upper()

    # Store 1 specific mapping
    if "store_1" in fn or "store 1" in fn or store_upper in ("STORE_1", "STORE-1", "ST1076"):
        if "cam 3" in fn or "entry" in fn:
            return {"id": "CAM_3", "role": "entrance", "zone": "entrance"}
        elif "cam 5" in fn or "billing" in fn:
            return {"id": "CAM_5", "role": "zone", "zone": "billing"}
        elif "cam 1" in fn:
            return {"id": "CAM_1", "role": "zone", "zone": "skincare"}
        elif "cam 2" in fn:
            return {"id": "CAM_2", "role": "zone", "zone": "makeup"}

    # Store 2 specific mapping
    if "store_2" in fn or "store 2" in fn or store_upper in ("STORE_2", "STORE-2"):
        if "entry 1" in fn or "entry_1" in fn:
            return {"id": "ENTRY_1", "role": "entrance", "zone": "entrance"}
        elif "entry 2" in fn or "entry_2" in fn:
            return {"id": "ENTRY_2", "role": "entrance", "zone": "entrance"}
        elif "billing" in fn:
            return {"id": "BILLING", "role": "zone", "zone": "billing"}
        elif "zone" in fn:
            return {"id": "ZONE", "role": "zone", "zone": "makeup"}

    # Generic Fallbacks
    if "entry" in fn or "entrance" in fn:
        return {"id": "CAM_ENTRY", "role": "entrance", "zone": "entrance"}
    elif "billing" in fn:
        return {"id": "CAM_BILLING", "role": "zone", "zone": "billing"}
    elif "makeup" in fn:
        return {"id": "CAM_MAKEUP", "role": "zone", "zone": "makeup"}
    elif "skincare" in fn:
        return {"id": "CAM_SKINCARE", "role": "zone", "zone": "skincare"}
    else:
        return {"id": "CAM_FLOOR", "role": "zone", "zone": "floor"}


def process_entrance_camera(
    store_id: str,
    tracker: PersonTracker,
    video_path: str,
    camera_id: str,
    r: redis.Redis,
) -> dict:
    """
    Process the entrance camera for entry/exit detection.
    """
    logger.info("detector.processing_entrance", store=store_id, camera=camera_id, video=video_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("detector.video_open_failed", video=video_path)
        return {"entries": 0, "exits": 0, "error": "Cannot open video"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_skip = max(1, int(fps / Config.TARGET_FPS))

    # Initialize line crossing detector
    line_detector = LineCrossingDetector()

    frame_idx = 0
    processed_frames = 0
    events_generated = 0

    # Update processing status
    publish_event(r, {
        "event_id": str(uuid.uuid4()),
        "event_type": "processing_status",
        "camera_id": camera_id,
        "store_id": store_id,
        "status": "processing",
        "total_frames": str(total_frames),
        "timestamp": datetime.now().isoformat(),
    })

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        if frame_idx % frame_skip != 0:
            continue

        processed_frames += 1

        # Run detection + tracking
        detections = tracker.process_frame(frame, frame_idx)

        for det in detections:
            track_id = det["track_id"]
            cx, cy = det["centroid"]

            crossing = line_detector.update(track_id, cy, frame_idx)

            if crossing:
                timestamp = get_video_timestamp(frame, fps, frame_idx)
                event = {
                    "event_id": str(uuid.uuid4()),
                    "store_id": store_id,
                    "camera_id": camera_id,
                    "visitor_id": f"VIS_{track_id}",
                    "event_type": crossing.upper(),  # ENTRY or EXIT
                    "timestamp": timestamp,
                    "zone_id": "ENTRANCE",
                    "dwell_ms": 0,
                    "is_staff": "False",
                    "confidence": str(det["confidence"]),
                    "bbox_x1": str(det["bbox"][0]),
                    "bbox_y1": str(det["bbox"][1]),
                    "bbox_x2": str(det["bbox"][2]),
                    "bbox_y2": str(det["bbox"][3]),
                    "frame_number": str(frame_idx),
                }
                publish_event(r, event)
                events_generated += 1

        if processed_frames % 50 == 0:
            logger.info(
                "detector.entrance_progress",
                camera=camera_id,
                frame=frame_idx,
                total=total_frames,
                pct=round(frame_idx / total_frames * 100, 1),
                entries=line_detector.total_entries,
                exits=line_detector.total_exits,
            )

    cap.release()

    stats = line_detector.get_stats()
    logger.info(
        "detector.entrance_complete",
        camera=camera_id,
        processed_frames=processed_frames,
        total_frames=total_frames,
        **stats,
    )

    publish_event(r, {
        "event_id": str(uuid.uuid4()),
        "event_type": "processing_status",
        "camera_id": camera_id,
        "store_id": store_id,
        "status": "completed",
        "frames_processed": str(processed_frames),
        "total_frames": str(total_frames),
        "events_generated": str(events_generated),
        "entries": str(stats["total_entries"]),
        "exits": str(stats["total_exits"]),
        "timestamp": datetime.now().isoformat(),
    })

    return stats


def process_zone_camera(
    store_id: str,
    tracker: PersonTracker,
    video_path: str,
    camera_id: str,
    zone_name: str,
    r: redis.Redis,
) -> dict:
    """
    Process an interior zone camera for dwell time analysis.
    """
    logger.info(
        "detector.processing_zone",
        store=store_id,
        camera=camera_id,
        zone=zone_name,
        video=video_path,
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("detector.video_open_failed", video=video_path)
        return {"zone": zone_name, "error": "Cannot open video"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_skip = max(1, int(fps / Config.TARGET_FPS))

    zone_analyzer = ZoneAnalyzer(camera_id, zone_name, fps)

    frame_idx = 0
    processed_frames = 0

    publish_event(r, {
        "event_id": str(uuid.uuid4()),
        "event_type": "processing_status",
        "camera_id": camera_id,
        "store_id": store_id,
        "status": "processing",
        "total_frames": str(total_frames),
        "timestamp": datetime.now().isoformat(),
    })

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        if frame_idx % frame_skip != 0:
            continue

        processed_frames += 1
        detections = tracker.process_frame(frame, frame_idx)

        for det in detections:
            zone_analyzer.update(det["track_id"], frame_idx)

        if processed_frames % 50 == 0:
            logger.info(
                "detector.zone_progress",
                camera=camera_id,
                zone=zone_name,
                frame=frame_idx,
                total=total_frames,
                pct=round(frame_idx / total_frames * 100, 1),
            )

    cap.release()

    # Identify likely staff
    staff_ids = zone_analyzer.identify_likely_staff(processed_frames)

    # Get dwell times and publish events
    dwell_times = zone_analyzer.get_dwell_times()
    events_generated = 0

    for dwell in dwell_times:
        is_staff = dwell["track_id"] in staff_ids
        timestamp = get_video_timestamp(None, fps, dwell["first_frame"])
        event = {
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "camera_id": camera_id,
            "visitor_id": f"VIS_{dwell['track_id']}",
            "event_type": "ZONE_DWELL",
            "timestamp": timestamp,
            "zone_id": zone_name.upper(),
            "dwell_ms": int(dwell["dwell_seconds"] * 1000),
            "is_staff": str(is_staff),
            "confidence": "0.90",
            "frame_number": str(dwell["first_frame"]),
        }
        publish_event(r, event)
        events_generated += 1

    logger.info(
        "detector.zone_complete",
        camera=camera_id,
        zone=zone_name,
        processed_frames=processed_frames,
        dwell_events=len(dwell_times),
        staff_detected=len(staff_ids),
    )

    publish_event(r, {
        "event_id": str(uuid.uuid4()),
        "event_type": "processing_status",
        "camera_id": camera_id,
        "store_id": store_id,
        "status": "completed",
        "frames_processed": str(processed_frames),
        "total_frames": str(total_frames),
        "events_generated": str(events_generated),
        "timestamp": datetime.now().isoformat(),
    })

    return {
        "zone": zone_name,
        "dwell_events": len(dwell_times),
        "staff_ids": list(staff_ids),
    }


def main():
    """Main entry point for the detector service."""
    logger.info("detector.starting", video_dir=Config.VIDEO_DIR)

    # Wait for Redis to be ready
    r = None
    for attempt in range(30):
        try:
            r = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                decode_responses=True,
            )
            r.ping()
            logger.info("detector.redis_connected")
            break
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("detector.redis_waiting", attempt=attempt + 1)
            time.sleep(2)

    if r is None:
        logger.error("detector.redis_connection_failed")
        sys.exit(1)

    # Discover video files recursively
    video_dir = Path(Config.VIDEO_DIR)
    if not video_dir.exists():
        logger.error("detector.video_dir_not_found", path=str(video_dir))
        sys.exit(1)

    video_files = sorted(video_dir.glob("**/*.mp4"))
    if not video_files:
        logger.error("detector.no_videos_found", path=str(video_dir))
        sys.exit(1)

    logger.info("detector.videos_found", count=len(video_files),
                files=[f.relative_to(video_dir).as_posix() for f in video_files])

    # Process each camera video file
    all_results = {}

    for video_file in video_files:
        # Determine store_id from parent directory name
        # e.g., if path is data/videos/Store 1/CAM 1 - zone.mp4, store_id is STORE_1
        parent_name = video_file.parent.name
        store_id = parent_name.upper().replace(" ", "_")
        if store_id == "VIDEOS":
            # Fallback if flat directory
            store_id = "STORE_1"

        # Map camera configurations dynamically
        camera_config = map_camera_config(store_id, video_file.name)
        camera_id = camera_config["id"]
        role = camera_config["role"]
        zone = camera_config["zone"]

        # Create fresh tracker for each camera
        tracker = PersonTracker()
        start_time = time.time()

        if role == "entrance":
            result = process_entrance_camera(
                store_id, tracker, str(video_file), camera_id, r
            )
        elif role == "zone":
            result = process_zone_camera(
                store_id, tracker, str(video_file), camera_id, zone, r
            )
        else:
            logger.warning("detector.unknown_role", role=role)
            continue

        elapsed = time.time() - start_time
        result["processing_time_seconds"] = round(elapsed, 1)
        
        # Scope results by store_id and camera_id
        store_results = all_results.setdefault(store_id, {})
        store_results[camera_id] = result

        logger.info(
            "detector.camera_done",
            store=store_id,
            camera=camera_id,
            role=role,
            elapsed=f"{elapsed:.1f}s",
        )

    # Signal processing complete for all stores
    publish_event(r, {
        "event_id": str(uuid.uuid4()),
        "event_type": "processing_status",
        "camera_id": "ALL",
        "store_id": "ALL",
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
    })

    logger.info(
        "detector.all_complete",
        results=all_results,
    )


if __name__ == "__main__":
    main()
