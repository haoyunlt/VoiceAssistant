"""多模态检索服务 - 支持图像和文本的联合检索"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MultimodalRetrievalService:
    """
    多模态检索服务

    支持的功能：
    1. 图像检索：以图搜图
    2. 文本检索图像：用文本描述搜索图像
    3. 图像检索文本：用图像搜索相关文本
    4. 联合检索：同时使用图像和文本进行检索
    5. 跨模态对齐：确保图像和文本在同一语义空间
    """

    def __init__(self, vector_store_client, image_encoder, text_encoder):
        """
        初始化多模态检索服务

        Args:
            vector_store_client: 向量存储客户端
            image_encoder: 图像编码器（如CLIP）
            text_encoder: 文本编码器
        """
        self.vector_store = vector_store_client
        self.image_encoder = image_encoder
        self.text_encoder = text_encoder

    async def search_by_image(
        self,
        image_data: bytes,
        tenant_id: str,
        knowledge_base_id: str | None = None,
        top_k: int = 10,
        modality_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        以图搜索

        Args:
            image_data: 图像数据
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回结果数
            modality_filter: 模态过滤（'image', 'text', None表示全部）

        Returns:
            检索结果列表
        """
        logger.info(f"Searching by image, top_k={top_k}, filter={modality_filter}")

        # 1. 图像编码
        image_embedding = await self._encode_image(image_data)

        # 2. 向量检索
        results = await self.vector_store.search(
            embedding=image_embedding,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k * 2,  # 多取一些，用于过滤
            metadata_filter={},
        )

        # 3. 模态过滤
        if modality_filter:
            results = [r for r in results if r.get("modality") == modality_filter]

        # 4. 重排序（考虑多模态相关性）
        reranked_results = await self._rerank_multimodal(
            query_type="image", query_data=image_data, results=results
        )

        return reranked_results[:top_k]

    async def search_by_text(
        self,
        text: str,
        tenant_id: str,
        knowledge_base_id: str | None = None,
        top_k: int = 10,
        modality_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        文本搜索（可以搜索图像或文本）

        Args:
            text: 查询文本
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回结果数
            modality_filter: 模态过滤

        Returns:
            检索结果列表
        """
        logger.info(f"Searching by text: {text[:50]}, filter={modality_filter}")

        # 1. 文本编码
        text_embedding = await self._encode_text(text)

        # 2. 向量检索
        results = await self.vector_store.search(
            embedding=text_embedding,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k * 2,
            metadata_filter={},
        )

        # 3. 模态过滤
        if modality_filter:
            results = [r for r in results if r.get("modality") == modality_filter]

        # 4. 重排序
        reranked_results = await self._rerank_multimodal(
            query_type="text", query_data=text, results=results
        )

        return reranked_results[:top_k]

    async def search_hybrid(
        self,
        text: str,
        tenant_id: str,
        image_data: bytes | None = None,
        knowledge_base_id: str | None = None,
        top_k: int = 10,
        text_weight: float = 0.5,
        image_weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        混合检索（文本+图像）

        Args:
            text: 查询文本
            image_data: 查询图像（可选）
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回结果数
            text_weight: 文本权重
            image_weight: 图像权重

        Returns:
            检索结果列表
        """
        logger.info(f"Hybrid search: text={text[:50]}, has_image={image_data is not None}")

        # 1. 编码
        text_embedding = await self._encode_text(text)

        if image_data:
            image_embedding = await self._encode_image(image_data)

            # 融合embeddings
            combined_embedding = self._fuse_embeddings(
                text_embedding, image_embedding, text_weight, image_weight
            )
        else:
            combined_embedding = text_embedding

        # 2. 检索
        results = await self.vector_store.search(
            embedding=combined_embedding,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k * 2,
            metadata_filter={},
        )

        # 3. 重排序
        reranked_results = await self._rerank_multimodal(
            query_type="hybrid", query_data={"text": text, "image": image_data}, results=results
        )

        return reranked_results[:top_k]

    async def index_document(
        self,
        document_id: str,
        content: str,
        images: list[bytes] | None = None,
        metadata: dict | None = None,
        tenant_id: str = None,
    ) -> dict[str, Any]:
        """
        索引多模态文档

        Args:
            document_id: 文档ID
            content: 文本内容
            images: 图像列表
            metadata: 元数据
            tenant_id: 租户ID

        Returns:
            索引结果
        """
        logger.info(f"Indexing multimodal document: {document_id}")

        indexed_chunks = []

        # 1. 索引文本
        if content:
            text_chunks = self._split_text(content)

            for i, chunk in enumerate(text_chunks):
                chunk_id = f"{document_id}_text_{i}"
                embedding = await self._encode_text(chunk)

                await self.vector_store.insert(
                    id=chunk_id,
                    embedding=embedding,
                    metadata={
                        "document_id": document_id,
                        "modality": "text",
                        "content": chunk,
                        "chunk_index": i,
                        "tenant_id": tenant_id,
                        **(metadata or {}),
                    },
                )

                indexed_chunks.append({"chunk_id": chunk_id, "modality": "text", "index": i})

        # 2. 索引图像
        if images:
            for i, image_data in enumerate(images):
                chunk_id = f"{document_id}_image_{i}"
                embedding = await self._encode_image(image_data)

                # 可选：生成图像描述
                image_caption = await self._generate_image_caption(image_data)

                await self.vector_store.insert(
                    id=chunk_id,
                    embedding=embedding,
                    metadata={
                        "document_id": document_id,
                        "modality": "image",
                        "caption": image_caption,
                        "image_index": i,
                        "tenant_id": tenant_id,
                        **(metadata or {}),
                    },
                )

                indexed_chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "modality": "image",
                        "index": i,
                        "caption": image_caption,
                    }
                )

        logger.info(f"Indexed {len(indexed_chunks)} chunks for document {document_id}")

        return {
            "success": True,
            "document_id": document_id,
            "indexed_chunks": len(indexed_chunks),
            "chunks": indexed_chunks,
        }

    async def _encode_image(self, _image_data: bytes) -> list[float]:
        """
        编码图像为向量

        实际实现需要使用CLIP等多模态模型
        """
        if not self.image_encoder:
            raise NotImplementedError("Image encoder not configured")

        # TODO: 使用实际的图像编码器
        # embedding = self.image_encoder.encode(image_data)

        # 模拟返回
        import random

        return [random.random() for _ in range(512)]

    async def _encode_text(self, _text: str) -> list[float]:
        """编码文本为向量"""
        if not self.text_encoder:
            raise NotImplementedError("Text encoder not configured")

        # TODO: 使用实际的文本编码器
        # embedding = self.text_encoder.encode(text)

        # 模拟返回
        import random

        return [random.random() for _ in range(512)]

    def _fuse_embeddings(
        self, text_emb: list[float], image_emb: list[float], text_weight: float, image_weight: float
    ) -> list[float]:
        """融合文本和图像向量"""
        # 加权平均
        fused = [
            t * text_weight + i * image_weight for t, i in zip(text_emb, image_emb, strict=False)
        ]

        # 归一化
        import math

        norm = math.sqrt(sum(x * x for x in fused))
        if norm > 0:
            fused = [x / norm for x in fused]

        return fused

    async def _rerank_multimodal(
        self, query_type: str, _query_data: Any, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        多模态重排序

        考虑因素：
        1. 原始相似度分数
        2. 模态匹配度
        3. 内容质量
        """
        for result in results:
            # 基础分数
            base_score = result.get("score", 0.0)

            # 模态匹配加分
            result_modality = result.get("modality", "text")
            modality_boost = 0.0

            if query_type == result_modality:
                modality_boost = 0.1
            elif query_type == "hybrid":
                modality_boost = 0.05

            # 最终分数
            result["final_score"] = base_score + modality_boost

        # 按最终分数排序
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        return results

    async def _generate_image_caption(self, _image_data: bytes) -> str:
        """
        生成图像描述

        实际实现需要使用图像描述模型（如BLIP）
        """
        # TODO: 使用实际的图像描述模型
        return "Generated caption for image"

    def _split_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """分割文本"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)

        return chunks

    async def get_statistics(
        self, _tenant_id: str, _knowledge_base_id: str | None = None
    ) -> dict[str, Any]:
        """
        获取多模态索引统计

        Args:
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID

        Returns:
            统计信息
        """
        # TODO: 从向量存储获取实际统计
        return {
            "total_documents": 0,
            "text_chunks": 0,
            "image_chunks": 0,
            "total_chunks": 0,
            "by_modality": {"text": 0, "image": 0},
        }

    async def delete_document(self, document_id: str, _tenant_id: str) -> dict[str, Any]:
        """
        删除文档的所有模态数据

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            删除结果
        """
        logger.info(f"Deleting multimodal document: {document_id}")

        # TODO: 从向量存储删除所有相关chunk
        deleted_count = 0

        return {"success": True, "document_id": document_id, "deleted_chunks": deleted_count}
