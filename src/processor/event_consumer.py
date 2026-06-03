"""
Redis event consumer for the API service.

Runs as a background task, consuming events from the Redis Stream
published by the detector service. Events are stored in SQLite
for API query access.
"""
import time
import threading
from typing import Optional

import redis
import structlog

from src.config import Config
from src.database import Database
from src.schemas import StoreEvent

logger = structlog.get_logger("event_consumer")


class EventConsumer:
    """
    Consumes events from Redis Streams and stores them in SQLite.

    Uses Redis consumer groups for reliable delivery. If the consumer
    crashes and restarts, it picks up from where it left off.
    """

    def __init__(self, db: Database, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis_client = redis_client
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.events_consumed = 0
        self.detection_complete = False

    def connect_redis(self) -> bool:
        """Connect to Redis, creating consumer group if needed."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    decode_responses=True,
                )
                self.redis_client.ping()
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.error("consumer.redis_connect_failed", error=str(e))
                return False

        # Create consumer group (ignore if already exists)
        try:
            self.redis_client.xgroup_create(
                Config.REDIS_EVENTS_STREAM,
                Config.REDIS_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info("consumer.group_created", group=Config.REDIS_CONSUMER_GROUP)
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info("consumer.group_exists", group=Config.REDIS_CONSUMER_GROUP)
            else:
                logger.error("consumer.group_create_failed", error=str(e))
                return False

        return True

    def start(self) -> None:
        """Start consuming events in a background thread."""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info("consumer.started")

    def stop(self) -> None:
        """Stop the consumer."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("consumer.stopped", events_consumed=self.events_consumed)

    def _consume_loop(self) -> None:
        """Main consumption loop."""
        # Wait for Redis connection
        connected = False
        for attempt in range(60):
            if not self.running:
                return
            connected = self.connect_redis()
            if connected:
                break
            time.sleep(2)

        if not connected:
            logger.error("consumer.failed_to_connect")
            return

        logger.info("consumer.consuming", stream=Config.REDIS_EVENTS_STREAM)

        while self.running:
            try:
                # Read new messages from the stream
                messages = self.redis_client.xreadgroup(
                    Config.REDIS_CONSUMER_GROUP,
                    Config.REDIS_CONSUMER_NAME,
                    {Config.REDIS_EVENTS_STREAM: ">"},
                    count=100,
                    block=2000,  # block for 2 seconds
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        self._process_message(msg_id, msg_data)

            except redis.ConnectionError:
                logger.warning("consumer.redis_disconnected")
                time.sleep(5)
                self.connect_redis()
            except Exception as e:
                logger.error("consumer.error", error=str(e))
                time.sleep(1)

    def _process_message(self, msg_id: str, data: dict) -> None:
        """Process a single message from the stream."""
        event_type = data.get("event_type", "")

        # Handle processing status messages
        if event_type == "processing_status":
            camera_id = data.get("camera_id", "")
            status = data.get("status", "")

            self.db.update_processing_status(
                camera_id=camera_id,
                status=status,
                frames_processed=int(data.get("frames_processed", 0)),
                total_frames=int(data.get("total_frames", 0)),
                events_generated=int(data.get("events_generated", 0)),
                started_at=data.get("timestamp") if status == "processing" else None,
                completed_at=data.get("timestamp") if status == "completed" else None,
            )

            if camera_id == "ALL" and status == "completed":
                self.detection_complete = True
                logger.info("consumer.detection_complete")

            # Acknowledge the message
            try:
                self.redis_client.xack(
                    Config.REDIS_EVENTS_STREAM,
                    Config.REDIS_CONSUMER_GROUP,
                    msg_id,
                )
            except Exception:
                pass
            return

        # Store regular events in the database
        try:
            # Coerce 'is_staff' string if needed
            is_staff_val = data.get("is_staff", "False")
            if isinstance(is_staff_val, str):
                data["is_staff"] = is_staff_val.lower() == "true"

            # Parse and validate with StoreEvent model
            event = StoreEvent(**data)
            event_dict = {
                "event_id": event.event_id,
                "store_id": event.store_id,
                "camera_id": event.camera_id,
                "visitor_id": event.visitor_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "zone_id": event.zone_id,
                "dwell_ms": event.dwell_ms,
                "is_staff": event.is_staff,
                "confidence": event.confidence,
                "metadata": event.metadata,
            }
            self.db.insert_event(event_dict)
            self.events_consumed += 1
        except Exception as e:
            logger.error("consumer.validation_failed", error=str(e), data=data)

        # Acknowledge
        try:
            self.redis_client.xack(
                Config.REDIS_EVENTS_STREAM,
                Config.REDIS_CONSUMER_GROUP,
                msg_id,
            )
        except Exception:
            pass

        if self.events_consumed % 50 == 0:
            logger.info("consumer.progress", events=self.events_consumed)
