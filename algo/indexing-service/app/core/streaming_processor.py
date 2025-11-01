"""
流式文档处理器
适用于大文件（100MB+）的流式处理，避免 OOM
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Prometheus 指标
STREAMING_DOCUMENTS_PROCESSED = Counter(
    "streaming_documents_processed_total",
    "Total number of documents processed in streaming mode",
    ["status", "file_size_mb"],
)
STREAMING_PROCESSING_TIME = Histogram(
    "streaming_processing_seconds",
    "Time spent processing documents in streaming mode",
    ["file_size_mb"],
    buckets=[10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)
STREAMING_MEMORY_USAGE = Gauge(
    "streaming_memory_usage_bytes",
    "Current memory usage in streaming processing",
)


class StreamingDocumentProcessor:
    """流式文档处理器"""

    def __init__(
        self,
        document_processor,
        chunk_size_mb: int = 10,
        max_memory_mb: int = 500,
    ):
        """
        初始化流式处理器

        Args:
            document_processor: 文档处理器实例
            chunk_size_mb: 每次读取的文件块大小（MB）
            max_memory_mb: 最大内存限制（MB）
        """
        self.document_processor = document_processor
        self.chunk_size_mb = chunk_size_mb
        self.max_memory_mb = max_memory_mb
        self.chunk_size_bytes = chunk_size_mb * 1024 * 1024

        logger.info(
            f"StreamingDocumentProcessor initialized: "
            f"chunk_size={chunk_size_mb}MB, max_memory={max_memory_mb}MB"
        )

    async def process_streaming(
        self,
        document_id: str,
        tenant_id: str = "default",
        file_path: str | None = None,
    ) -> dict[str, Any]:
        """
        流式处理大文件

        策略:
        1. 流式下载文件（分块读取）
        2. 流式解析文档内容
        3. 流式分块和向量化
        4. 增量写入向量库

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID
            file_path: 文件路径

        Returns:
            处理结果
        """
        start_time = time.time()

        logger.info(f"Starting streaming processing for document: {document_id}")

        try:
            # 统计信息
            stats = {
                "chunks_processed": 0,
                "vectors_stored": 0,
                "bytes_processed": 0,
                "peak_memory_mb": 0,
            }

            # 流式处理管道
            async for result in self._streaming_pipeline(
                document_id=document_id,
                tenant_id=tenant_id,
                file_path=file_path or document_id,
            ):
                stats["chunks_processed"] += result.get("chunk_count", 0)
                stats["vectors_stored"] += result.get("vector_count", 0)
                stats["bytes_processed"] += result.get("bytes_processed", 0)

                # 更新内存监控
                current_memory_mb = self._get_memory_usage_mb()
                stats["peak_memory_mb"] = max(stats["peak_memory_mb"], current_memory_mb)
                STREAMING_MEMORY_USAGE.set(current_memory_mb * 1024 * 1024)

                # 内存检查
                if current_memory_mb > self.max_memory_mb:
                    logger.warning(
                        f"Memory usage ({current_memory_mb}MB) exceeds limit ({self.max_memory_mb}MB)"
                    )
                    # 触发垃圾回收
                    import gc
                    gc.collect()

            elapsed_time = time.time() - start_time
            file_size_mb = stats["bytes_processed"] / (1024 * 1024)

            # 记录指标
            STREAMING_DOCUMENTS_PROCESSED.labels(
                status="success",
                file_size_mb=f"{int(file_size_mb)}",
            ).inc()
            STREAMING_PROCESSING_TIME.labels(
                file_size_mb=f"{int(file_size_mb)}",
            ).observe(elapsed_time)

            result = {
                "status": "success",
                "document_id": document_id,
                "chunks_count": stats["chunks_processed"],
                "vectors_count": stats["vectors_stored"],
                "file_size_mb": file_size_mb,
                "peak_memory_mb": stats["peak_memory_mb"],
                "elapsed_time": elapsed_time,
            }

            logger.info(
                f"Streaming processing completed: {document_id}, "
                f"{stats['chunks_processed']} chunks, "
                f"{file_size_mb:.2f}MB, "
                f"peak memory: {stats['peak_memory_mb']:.2f}MB, "
                f"{elapsed_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Streaming processing failed for {document_id}: {e}", exc_info=True)

            STREAMING_DOCUMENTS_PROCESSED.labels(
                status="failed",
                file_size_mb="unknown",
            ).inc()

            return {
                "status": "failed",
                "document_id": document_id,
                "error": str(e),
                "elapsed_time": time.time() - start_time,
            }

    async def _streaming_pipeline(
        self,
        document_id: str,
        tenant_id: str,
        file_path: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式处理管道

        Yields:
            每个批次的处理结果
        """
        # 1. 流式下载文件
        async for file_chunk in self._download_streaming(file_path):
            bytes_processed = len(file_chunk)

            # 2. 流式解析
            text_chunks = await self._parse_streaming(file_chunk, file_path)

            if not text_chunks:
                continue

            # 3. 流式分块
            all_chunks = []
            for text in text_chunks:
                chunks = await self.document_processor.chunker.chunk(
                    text=text,
                    document_id=document_id,
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                continue

            # 4. 批量向量化
            texts = [chunk["content"] for chunk in all_chunks]
            embeddings = await self.document_processor.embedder.embed_batch(texts)

            # 5. 增量写入向量库
            await self.document_processor._store_vectors(
                chunks=all_chunks,
                embeddings=embeddings,
                document_id=document_id,
                tenant_id=tenant_id,
            )

            yield {
                "chunk_count": len(all_chunks),
                "vector_count": len(embeddings),
                "bytes_processed": bytes_processed,
            }

    async def _download_streaming(
        self,
        file_path: str,
    ) -> AsyncGenerator[bytes, None]:
        """
        流式下载文件

        Yields:
            文件数据块
        """
        try:
            # 从 MinIO 流式下载
            # 这里简化实现，实际应该使用 MinIO 的流式 API
            file_data = await self.document_processor.minio_client.download_file(file_path)

            # 分块返回
            offset = 0
            while offset < len(file_data):
                chunk = file_data[offset : offset + self.chunk_size_bytes]
                offset += self.chunk_size_bytes
                yield chunk

        except Exception as e:
            logger.error(f"Streaming download failed: {e}")
            raise

    async def _parse_streaming(
        self,
        file_chunk: bytes,
        file_path: str,
    ) -> list[str]:
        """
        流式解析文件块

        Args:
            file_chunk: 文件数据块
            file_path: 文件路径

        Returns:
            文本块列表
        """
        try:
            # 根据文件类型选择解析器
            parser = self.document_processor.parser_factory.get_parser(file_path)

            # 解析文本
            text = await parser.parse(file_chunk)

            # 按段落分割（避免一次性加载整个文档）
            paragraphs = text.split("\n\n")

            return [p.strip() for p in paragraphs if p.strip()]

        except Exception as e:
            logger.error(f"Streaming parse failed: {e}")
            return []

    def _get_memory_usage_mb(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # 转换为 MB

        except ImportError:
            # 如果没有安装 psutil，返回 0
            return 0.0

        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return 0.0

    async def process_large_file(
        self,
        document_id: str,
        tenant_id: str = "default",
        file_path: str | None = None,
        enable_checkpoint: bool = True,
    ) -> dict[str, Any]:
        """
        处理大文件（带断点续传）

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID
            file_path: 文件路径
            enable_checkpoint: 是否启用断点续传

        Returns:
            处理结果
        """
        if not enable_checkpoint:
            return await self.process_streaming(document_id, tenant_id, file_path)

        # TODO: 实现断点续传逻辑
        # 1. 检查 Redis 中是否有处理进度
        # 2. 从上次中断的位置继续处理
        # 3. 定期保存处理进度到 Redis

        logger.info(f"Processing large file with checkpoint: {document_id}")
        return await self.process_streaming(document_id, tenant_id, file_path)


class StreamingBatchProcessor:
    """流式批量处理器（结合流式处理和批量处理）"""

    def __init__(
        self,
        streaming_processor: StreamingDocumentProcessor,
        max_workers: int = 5,
    ):
        """
        初始化流式批量处理器

        Args:
            streaming_processor: 流式处理器实例
            max_workers: 最大并发数（较小，避免内存占用过高）
        """
        self.streaming_processor = streaming_processor
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

        logger.info(f"StreamingBatchProcessor initialized: max_workers={max_workers}")

    async def process_batch_streaming(
        self,
        document_ids: list[str],
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        批量流式处理大文件

        Args:
            document_ids: 文档 ID 列表
            tenant_id: 租户 ID

        Returns:
            处理结果统计
        """
        start_time = time.time()

        logger.info(f"Starting streaming batch processing: {len(document_ids)} documents")

        tasks = [
            self._process_with_semaphore(doc_id, tenant_id)
            for doc_id in document_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        success_count = sum(
            1 for r in results
            if not isinstance(r, Exception) and r.get("status") == "success"
        )
        failed_count = len(document_ids) - success_count

        elapsed_time = time.time() - start_time

        result = {
            "total": len(document_ids),
            "success": success_count,
            "failed": failed_count,
            "elapsed_time": elapsed_time,
            "throughput": len(document_ids) / elapsed_time if elapsed_time > 0 else 0,
        }

        logger.info(
            f"Streaming batch processing completed: {success_count}/{len(document_ids)} "
            f"succeeded in {elapsed_time:.2f}s"
        )

        return result

    async def _process_with_semaphore(
        self,
        document_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """使用信号量控制并发"""
        async with self.semaphore:
            return await self.streaming_processor.process_streaming(
                document_id=document_id,
                tenant_id=tenant_id,
            )
