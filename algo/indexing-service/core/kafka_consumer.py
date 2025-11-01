"""
Kafka Consumer for document.uploaded events
"""

import json
import logging
from collections.abc import Callable

from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)


class DocumentEventConsumer:
    """Kafka consumer for document events"""

    def __init__(self, bootstrap_servers: str, group_id: str, topic: str):
        self.topic = topic
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to topic: {topic}")

    def consume(self, handler: Callable):
        """Consume messages and process with handler"""
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                try:
                    # Parse message
                    event = json.loads(msg.value().decode("utf-8"))
                    logger.info(f"Received event: {event.get('event_type')}")

                    # Process event
                    handler(event)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
        finally:
            self.consumer.close()

    def close(self):
        """Close consumer"""
        self.consumer.close()
