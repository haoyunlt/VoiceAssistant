"""
Kafka Consumer for Document Indexing
订阅 document.uploaded 事件并触发文档索引流程
"""

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from kafka import KafkaConsumer
from kafka.errors import KafkaError

# 导入自定义模块
from app.core.document_processor import DocumentProcessor
from app.core.embedder import TextEmbedder
from app.core.graph_builder import GraphBuilder
from app.infrastructure.milvus_client import MilvusClient
from app.infrastructure.minio_client import MinioClient
from app.infrastructure.neo4j_client import Neo4jClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentIndexingConsumer:
    """文档索引 Kafka 消费者"""

    def __init__(
        self,
        kafka_brokers: str = "localhost:9092",
        group_id: str = "indexing-service",
        topics: list = None,
        max_workers: int = 4,
    ):
        """
        初始化消费者

        Args:
            kafka_brokers: Kafka broker 地址
            group_id: 消费者组 ID
            topics: 订阅的 topic 列表
            max_workers: 最大并发处理数
        """
        self.kafka_brokers = kafka_brokers
        self.group_id = group_id
        self.topics = topics or ["document.events"]
        self.max_workers = max_workers

        # 初始化消费者（延迟到 start 方法）
        self.consumer: KafkaConsumer | None = None

        # 初始化处理器
        self.document_processor = DocumentProcessor()
        self.embedder = TextEmbedder()
        self.graph_builder = GraphBuilder()

        # 初始化基础设施客户端
        self.milvus_client = MilvusClient()
        self.neo4j_client = Neo4jClient()
        self.minio_client = MinioClient()

        # 线程池（用于并发处理）
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 统计信息
        self.stats = {"total_messages": 0, "successful": 0, "failed": 0, "skipped": 0}

    def start(self):
        """启动消费者"""
        try:
            logger.info(
                f"Starting Kafka consumer: brokers={self.kafka_brokers}, group={self.group_id}, topics={self.topics}"
            )

            # 创建 Kafka Consumer
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.kafka_brokers,
                group_id=self.group_id,
                enable_auto_commit=False,  # 手动提交偏移量
                auto_offset_reset="earliest",
                value_deserializer=lambda m: m,  # 保持原始字节，手动解析
                max_poll_records=10,  # 每次拉取最多 10 条消息
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )

            logger.info("Kafka consumer started successfully")

            # 开始消费消息
            self._consume_messages()

        except KafkaError as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting consumer: {e}")
            raise

    def _consume_messages(self):
        """消费消息主循环"""
        logger.info("Starting to consume messages...")

        try:
            for message in self.consumer:
                try:
                    self.stats["total_messages"] += 1

                    # 解析消息
                    event = self._parse_message(message)

                    if event is None:
                        self.stats["skipped"] += 1
                        continue

                    # 处理事件
                    success = self._handle_event(event)

                    if success:
                        self.stats["successful"] += 1
                        # 手动提交偏移量
                        self.consumer.commit()
                    else:
                        self.stats["failed"] += 1

                    # 定期输出统计信息
                    if self.stats["total_messages"] % 10 == 0:
                        self._log_stats()

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.stats["failed"] += 1

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def _parse_message(self, message) -> dict[str, Any] | None:
        """
        解析 Kafka 消息

        Returns:
            解析后的事件字典，如果解析失败返回 None
        """
        try:
            # 尝试解析为 JSON（简化版，实际应该解析 Protobuf）
            event = json.loads(message.value.decode("utf-8"))

            logger.debug(
                f"Parsed event: type={event.get('event_type')}, id={event.get('event_id')}"
            )

            return event

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            return None

    def _handle_event(self, event: dict[str, Any]) -> bool:
        """
        处理事件

        Args:
            event: 事件字典

        Returns:
            是否处理成功
        """
        event_type = event.get("event_type", "")

        # 根据事件类型分发
        if event_type == "document.uploaded":
            return self._handle_document_uploaded(event)
        elif event_type == "document.deleted":
            return self._handle_document_deleted(event)
        else:
            logger.debug(f"Ignoring event type: {event_type}")
            return True  # 忽略的事件也算成功

    def _handle_document_uploaded(self, event: dict[str, Any]) -> bool:
        """
        处理文档上传事件

        Args:
            event: 事件字典

        Returns:
            是否处理成功
        """
        try:
            # 提取事件信息
            payload = event.get("payload", {})
            document_id = payload.get("document_id")
            tenant_id = payload.get("tenant_id")
            filename = payload.get("filename")
            storage_path = payload.get("storage_path")
            content_type = payload.get("content_type")

            logger.info(f"Processing document upload: id={document_id}, file={filename}")

            # 1. 从 MinIO 下载文件
            logger.debug(f"Downloading file from MinIO: {storage_path}")
            file_content = self.minio_client.download_file(storage_path)

            if not file_content:
                logger.error(f"Failed to download file: {storage_path}")
                return False

            # 2. 解析文档
            logger.debug(f"Parsing document: {filename}")
            parsed_doc = self.document_processor.process_document(
                file_content=file_content, filename=filename, content_type=content_type
            )

            if not parsed_doc:
                logger.error(f"Failed to parse document: {filename}")
                return False

            # 3. 文本分块
            logger.debug(f"Chunking document: {len(parsed_doc.get('text', ''))} characters")
            chunks = self.document_processor.chunk_text(
                text=parsed_doc.get("text", ""), chunk_size=512, overlap=50
            )

            logger.info(f"Created {len(chunks)} chunks for document {document_id}")

            # 4. 向量化
            logger.debug(f"Embedding {len(chunks)} chunks")
            embeddings = []
            for chunk in chunks:
                embedding = self.embedder.embed_text(chunk["content"])
                embeddings.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "content": chunk["content"],
                        "embedding": embedding,
                        "metadata": {
                            "document_id": document_id,
                            "tenant_id": tenant_id,
                            "chunk_index": chunk["chunk_index"],
                            "start_offset": chunk["start_offset"],
                            "end_offset": chunk["end_offset"],
                        },
                    }
                )

            # 5. 存储到 Milvus
            logger.debug(f"Storing {len(embeddings)} embeddings to Milvus")
            vector_ids = self.milvus_client.insert_vectors(
                collection_name=f"documents_{tenant_id}", embeddings=embeddings
            )

            logger.info(f"Stored {len(vector_ids)} vectors for document {document_id}")

            # 6. 构建知识图谱（可选）
            if parsed_doc.get("entities"):
                logger.debug("Building knowledge graph")
                graph_stats = self.graph_builder.build_graph(
                    document_id=document_id,
                    entities=parsed_doc.get("entities", []),
                    relations=parsed_doc.get("relations", []),
                )
                logger.info(f"Built graph: {graph_stats}")

            # 7. 发布索引完成事件（TODO: 需要 Kafka Producer）
            logger.info(f"Document indexed successfully: {document_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to handle document uploaded event: {e}", exc_info=True)
            return False

    def _handle_document_deleted(self, event: dict[str, Any]) -> bool:
        """
        处理文档删除事件

        Args:
            event: 事件字典

        Returns:
            是否处理成功
        """
        try:
            payload = event.get("payload", {})
            document_id = payload.get("document_id")
            tenant_id = payload.get("tenant_id")

            logger.info(f"Processing document deletion: id={document_id}")

            # 1. 从 Milvus 删除向量
            deleted_count = self.milvus_client.delete_by_document_id(
                collection_name=f"documents_{tenant_id}", document_id=document_id
            )

            logger.info(f"Deleted {deleted_count} vectors for document {document_id}")

            # 2. 从 Neo4j 删除图节点
            if self.neo4j_client:
                self.neo4j_client.delete_document_nodes(document_id)

            logger.info(f"Document deleted successfully: {document_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to handle document deleted event: {e}", exc_info=True)
            return False

    def _log_stats(self):
        """输出统计信息"""
        logger.info(
            f"Stats: total={self.stats['total_messages']}, "
            f"success={self.stats['successful']}, "
            f"failed={self.stats['failed']}, "
            f"skipped={self.stats['skipped']}"
        )

    def stop(self):
        """停止消费者"""
        logger.info("Stopping Kafka consumer...")

        if self.consumer:
            self.consumer.close()

        if self.executor:
            self.executor.shutdown(wait=True)

        # 输出最终统计
        self._log_stats()

        logger.info("Kafka consumer stopped")


def main():
    """主函数"""
    # 从环境变量读取配置
    import os

    kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    group_id = os.getenv("KAFKA_GROUP_ID", "indexing-service")
    topics = os.getenv("KAFKA_TOPICS", "document.events").split(",")
    max_workers = int(os.getenv("MAX_WORKERS", "4"))

    # 创建并启动消费者
    consumer = DocumentIndexingConsumer(
        kafka_brokers=kafka_brokers, group_id=group_id, topics=topics, max_workers=max_workers
    )

    try:
        consumer.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Consumer failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
