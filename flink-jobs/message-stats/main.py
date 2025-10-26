"""Flink job for real-time message statistics."""

import logging
import sys
from datetime import timedelta

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.window import TumblingEventTimeWindows

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main Flink job entry point."""
    # Create execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(4)
    env.enable_checkpointing(60000)  # 60s checkpoint interval

    # Kafka source configuration
    kafka_source = (
        KafkaSource.builder()
        .set_bootstrap_servers("kafka:9092")
        .set_topics("conversation.messages")
        .set_group_id("flink-message-stats")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # Create data stream
    stream = env.from_source(
        kafka_source,
        WatermarkStrategy.for_bounded_out_of_orderness(timedelta(seconds=5)),
        "Kafka Source",
    )

    # Parse JSON and extract fields
    def parse_message(value):
        import json

        try:
            data = json.loads(value)
            return {
                "tenant_id": data.get("tenant_id"),
                "user_id": data.get("user_id"),
                "model": data.get("model"),
                "tokens_used": data.get("tokens_used", 0),
                "cost_usd": data.get("cost_usd", 0.0),
                "timestamp": data.get("timestamp"),
            }
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            return None

    parsed_stream = stream.map(parse_message, output_type=Types.PICKLED_BYTE_ARRAY()).filter(
        lambda x: x is not None
    )

    # TODO: Implement windowing and aggregation
    # Window by 1 minute and calculate:
    # - Total messages
    # - Total tokens
    # - Total cost
    # - Average latency

    # TODO: Sink to ClickHouse
    # parsed_stream.sink_to(clickhouse_sink)

    # Execute job
    env.execute("Message Statistics Job")


if __name__ == "__main__":
    main()

