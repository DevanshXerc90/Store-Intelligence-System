"""
Person detection and tracking using YOLOv8 + ByteTrack.
Processes video frames, detects persons, and maintains stable track IDs.
"""
import cv2
import numpy as np
import structlog
from ultralytics import YOLO

from src.config import Config

logger = structlog.get_logger(__name__)


class PersonTracker:
    """
    Wraps YOLOv8 with built-in ByteTrack for person detection and tracking.

    Design Decision: YOLOv8n (nano) chosen for speed over accuracy.
    Person detection doesn't require fine-grained class distinction —
    COCO class 0 (person) with confidence > 0.35 is sufficient for
    retail CCTV with decent lighting.
    """

    def __init__(self):
        logger.info("tracker.loading_model", model=Config.YOLO_MODEL)
        self.model = YOLO(Config.YOLO_MODEL)
        self.person_class = Config.PERSON_CLASS_ID
        self.min_confidence = Config.PERSON_CONFIDENCE
        self.min_bbox_area = Config.MIN_BBOX_AREA
        logger.info("tracker.model_loaded")

    def process_frame(
        self, frame: np.ndarray, frame_idx: int
    ) -> list[dict]:
        """
        Run detection + tracking on a single frame.

        Returns list of tracked persons:
        [
            {
                "track_id": int,
                "bbox": (x1, y1, x2, y2),
                "centroid": (cx, cy),
                "confidence": float,
                "bbox_area": float
            },
            ...
        ]
        """
        # Run YOLO with tracking (ByteTrack built-in)
        results = self.model.track(
            frame,
            persist=True,  # maintain track IDs across frames
            classes=[self.person_class],
            conf=self.min_confidence,
            iou=0.5,
            tracker="bytetrack.yaml",
            verbose=False,
        )

        detections = []
        if results and results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes

            for i in range(len(boxes)):
                # Get bounding box coordinates
                xyxy = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                # Filter by minimum area (removes small/distant detections)
                area = (x2 - x1) * (y2 - y1)
                if area < self.min_bbox_area:
                    continue

                # Get track ID (may be None if tracking not yet assigned)
                track_id = None
                if boxes.id is not None:
                    track_id = int(boxes.id[i].cpu().numpy())

                if track_id is None:
                    continue  # skip untracked detections

                confidence = float(boxes.conf[i].cpu().numpy())

                # Compute centroid
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                detections.append(
                    {
                        "track_id": track_id,
                        "bbox": (x1, y1, x2, y2),
                        "centroid": (cx, cy),
                        "confidence": confidence,
                        "bbox_area": area,
                    }
                )

        return detections

    def reset(self):
        """Reset tracker state for a new video."""
        self.model = YOLO(Config.YOLO_MODEL)
