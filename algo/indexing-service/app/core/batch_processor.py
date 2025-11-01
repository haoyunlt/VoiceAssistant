"""
批量文档处理器
支持并发控制和批量优化
"""

import asyncio
import logging
import time
from typing import Any

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Prometheus 指标
BATCH_PROCESSED = Counter(
    "batch_documents_processed_total",
    "Total number of documents processed in batch",
    ["status", "tenant_id"],
)
BATCH_PROCESSING_TIME = Histogram(
    "batch_processing_seconds",
    "Time spent processing document batch",
    ["tenant_id"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)


class BatchDocumentProcessor:
    """批量文档处理器"""

    def __init__(
        self,
        document_processor,
        max_workers: int = 10,
        batch_size: int = 32,
        timeout: float = 300.0,
    ):
        """
        初始化批量处理器

        Args:
            document_processor: 文档处理器实例
            max_workers: 最大并发数
            batch_size: 批量大小（用于向量化）
            timeout: 单个文档处理超时（秒）
        """
        self.document_processor = document_processor
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.timeout = timeout

        # 并发控制
        self.semaphore = asyncio.Semaphore(max_workers)

        logger.info(
            f"BatchDocumentProcessor initialized: max_workers={max_workers}, "
            f"batch_size={batch_size}, timeout={timeout}s"
        )

    async def process_batch(
        self,
        document_ids: list[str],
        tenant_id: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        批量处理文档

        Args:
            document_ids: 文档 ID 列表
            tenant_id: 租户 ID
            metadata: 元数据

        Returns:
            处理结果统计
        """
        start_time = time.time()
        metadata = metadata or {}

        logger.info(
            f"Starting batch processing: {len(document_ids)} documents "
            f"(tenant={tenant_id}, max_workers={self.max_workers})"
        )

        # 创建处理任务
        tasks = [
            self._process_document_with_semaphore(doc_id, tenant_id, metadata)
            for doc_id in document_ids
        ]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        success_count = 0
        failed_count = 0
        errors = []

        for doc_id, result in zip(document_ids, results, strict=False):
            if isinstance(result, Exception):
                failed_count += 1
                errors.append({"document_id": doc_id, "error": str(result)})
                BATCH_PROCESSED.labels(status="failed", tenant_id=tenant_id).inc()
                logger.error(f"Failed to process {doc_id}: {result}")
            elif result.get("status") == "success":
                success_count += 1
                BATCH_PROCESSED.labels(status="success", tenant_id=tenant_id).inc()
            else:
                failed_count += 1
                errors.append({"document_id": doc_id, "error": result.get("error")})
                BATCH_PROCESSED.labels(status="failed", tenant_id=tenant_id).inc()

        elapsed_time = time.time() - start_time
        BATCH_PROCESSING_TIME.labels(tenant_id=tenant_id).observe(elapsed_time)

        result = {
            "total": len(document_ids),
            "success": success_count,
            "failed": failed_count,
            "elapsed_time": elapsed_time,
            "throughput": len(document_ids) / elapsed_time if elapsed_time > 0 else 0,
            "errors": errors[:10],  # 只返回前 10 个错误
        }

        logger.info(
            f"Batch processing completed: {success_count}/{len(document_ids)} succeeded "
            f"in {elapsed_time:.2f}s (throughput: {result['throughput']:.2f} docs/s)"
        )

        return result

    async def _process_document_with_semaphore(
        self,
        document_id: str,
        tenant_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        使用信号量控制并发处理文档

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID
            metadata: 元数据

        Returns:
            处理结果
        """
        async with self.semaphore:
            try:
                # 使用超时控制
                result = await asyncio.wait_for(
                    self.document_processor.process_document(
                        document_id=document_id,
                        tenant_id=tenant_id,
                        user_id=metadata.get("user_id"),
                        file_path=metadata.get("file_path"),
                    ),
                    timeout=self.timeout,
                )
                return result

            except TimeoutError:
                logger.error(f"Document {document_id} processing timeout after {self.timeout}s")
                return {
                    "status": "failed",
                    "document_id": document_id,
                    "error": f"Timeout after {self.timeout}s",
                }

            except Exception as e:
                logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
                return {
                    "status": "failed",
                    "document_id": document_id,
                    "error": str(e),
                }

    async def process_with_priority(
        self,
        documents: list[dict[str, Any]],
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        按优先级批量处理文档

        Args:
            documents: 文档列表，每个包含 {id, priority, metadata}
            tenant_id: 租户 ID

        Returns:
            处理结果统计
        """
        # 按优先级排序（高优先级先处理）
        sorted_docs = sorted(
            documents,
            key=lambda x: x.get("priority", 0),
            reverse=True,
        )

        # 提取 document_ids
        document_ids = [doc["id"] for doc in sorted_docs]

        # 构建元数据映射
        metadata_map = {doc["id"]: doc.get("metadata", {}) for doc in sorted_docs}

        # 批量处理
        return await self.process_batch(
            document_ids=document_ids,
            tenant_id=tenant_id,
            metadata=metadata_map.get(document_ids[0], {}) if document_ids else {},
        )

    async def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "max_workers": self.max_workers,
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "active_tasks": self.max_workers - self.semaphore._value,
        }


class OptimizedBatchProcessor(BatchDocumentProcessor):
    """优化的批量处理器（带批量向量化）"""

    async def process_batch_optimized(
        self,
        document_ids: list[str],
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        优化的批量处理（批量向量化）

        策略:
        1. 并发下载和解析文档
        2. 批量分块
        3. 批量向量化（减少模型调用次数）
        4. 批量插入向量库

        Args:
            document_ids: 文档 ID 列表
            tenant_id: 租户 ID

        Returns:
            处理结果统计
        """
        start_time = time.time()

        logger.info(f"Starting optimized batch processing: {len(document_ids)} documents")

        try:
            # 1. 并发下载和解析
            download_tasks = [self._download_and_parse(doc_id) for doc_id in document_ids]
            parsed_docs = await asyncio.gather(*download_tasks, return_exceptions=True)

            # 2. 批量分块
            all_chunks = []
            doc_chunk_mapping = {}  # document_id -> chunk indices

            for doc_id, parsed_result in zip(document_ids, parsed_docs, strict=False):
                if isinstance(parsed_result, Exception):
                    logger.error(f"Failed to parse {doc_id}: {parsed_result}")
                    continue

                chunks = await self.document_processor.chunker.chunk(
                    text=parsed_result["text"],
                    document_id=doc_id,
                )

                start_idx = len(all_chunks)
                all_chunks.extend(chunks)
                end_idx = len(all_chunks)
                doc_chunk_mapping[doc_id] = (start_idx, end_idx)

            # 3. 批量向量化
            if all_chunks:
                texts = [chunk["content"] for chunk in all_chunks]
                embeddings = await self.document_processor.embedder.embed_batch(texts)

                # 4. 批量插入向量库
                await self.document_processor._store_vectors(
                    chunks=all_chunks,
                    embeddings=embeddings,
                    document_id="batch",  # 批量处理
                    tenant_id=tenant_id,
                )

            elapsed_time = time.time() - start_time

            result = {
                "total": len(document_ids),
                "success": len([d for d in parsed_docs if not isinstance(d, Exception)]),
                "failed": len([d for d in parsed_docs if isinstance(d, Exception)]),
                "total_chunks": len(all_chunks),
                "elapsed_time": elapsed_time,
                "throughput": len(document_ids) / elapsed_time if elapsed_time > 0 else 0,
            }

            logger.info(
                f"Optimized batch processing completed: {result['success']}/{len(document_ids)} "
                f"succeeded, {len(all_chunks)} chunks in {elapsed_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Optimized batch processing failed: {e}", exc_info=True)
            return {
                "total": len(document_ids),
                "success": 0,
                "failed": len(document_ids),
                "error": str(e),
                "elapsed_time": time.time() - start_time,
            }

    async def _download_and_parse(self, document_id: str) -> dict[str, Any]:
        """下载并解析文档"""
        file_data = await self.document_processor._download_document(document_id)
        text = await self.document_processor._parse_document(file_data, document_id)
        return {"document_id": document_id, "text": text}
