"""
Iter 1 & Iter 2 功能演示

展示批量处理、流式处理、智能分块、上下文增强等新功能
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_batch_processing():
    """演示批量文档处理"""
    logger.info("=== Demo: Batch Document Processing ===")

    from app.core.batch_processor import BatchDocumentProcessor
    from app.core.document_processor import DocumentProcessor

    # 初始化处理器
    document_processor = DocumentProcessor()
    await document_processor.initialize()

    batch_processor = BatchDocumentProcessor(
        document_processor=document_processor,
        max_workers=5,
        batch_size=16,
    )

    # 批量处理文档
    document_ids = [
        "doc_001", "doc_002", "doc_003",
        "doc_004", "doc_005",
    ]

    result = await batch_processor.process_batch(
        document_ids=document_ids,
        tenant_id="demo_tenant",
    )

    logger.info(f"Batch processing result: {result}")
    logger.info(f"Success rate: {result['success']/result['total']*100:.1f}%")
    logger.info(f"Throughput: {result['throughput']:.2f} docs/s")


async def demo_streaming_processing():
    """演示流式大文件处理"""
    logger.info("\n=== Demo: Streaming Large File Processing ===")

    from app.core.streaming_processor import StreamingDocumentProcessor
    from app.core.document_processor import DocumentProcessor

    # 初始化处理器
    document_processor = DocumentProcessor()
    await document_processor.initialize()

    streaming_processor = StreamingDocumentProcessor(
        document_processor=document_processor,
        chunk_size_mb=10,
        max_memory_mb=500,
    )

    # 流式处理大文件
    result = await streaming_processor.process_streaming(
        document_id="large_doc_001",
        tenant_id="demo_tenant",
        file_path="path/to/large/file.pdf",
    )

    logger.info(f"Streaming processing result: {result}")
    logger.info(f"File size: {result['file_size_mb']:.2f} MB")
    logger.info(f"Peak memory: {result['peak_memory_mb']:.2f} MB")


async def demo_task_queue():
    """演示任务队列"""
    logger.info("\n=== Demo: Task Queue with Priority ===")

    import redis.asyncio as redis
    from app.core.task_queue import IndexingTaskQueue, TaskPriority

    # 连接 Redis
    redis_client = await redis.from_url("redis://localhost:6379/0")

    # 初始化任务队列
    task_queue = IndexingTaskQueue(
        redis_client=redis_client,
        max_queue_size=1000,
    )

    # 加入任务（不同优先级）
    tasks = [
        ("urgent_doc", TaskPriority.URGENT),
        ("high_doc_1", TaskPriority.HIGH),
        ("normal_doc_1", TaskPriority.MEDIUM),
        ("high_doc_2", TaskPriority.HIGH),
        ("low_doc_1", TaskPriority.LOW),
    ]

    for doc_id, priority in tasks:
        task = await task_queue.enqueue(
            document_id=doc_id,
            tenant_id="demo_tenant",
            priority=priority,
            metadata={"source": "demo"},
        )
        logger.info(f"Enqueued: {task.task_id} (priority={priority.name})")

    # 从队列取任务（按优先级）
    logger.info("\nDequeuing tasks (by priority):")
    for _ in range(len(tasks)):
        task = await task_queue.dequeue()
        if task:
            logger.info(
                f"  - Dequeued: {task.document_id} "
                f"(priority={task.priority.name}, "
                f"wait_time={task.started_at - task.created_at:.2f}s)"
            )

    # 获取队列统计
    stats = await task_queue.get_queue_stats()
    logger.info(f"\nQueue stats: {stats}")

    await redis_client.close()


async def demo_semantic_chunking():
    """演示语义分块"""
    logger.info("\n=== Demo: Semantic Chunking ===")

    from app.core.semantic_chunker import SemanticChunker
    from app.core.embedder import BGE_M3_Embedder

    # 初始化
    embedder = BGE_M3_Embedder()
    chunker = SemanticChunker(
        embedder=embedder,
        similarity_threshold=0.75,
        min_chunk_size=100,
        max_chunk_size=800,
    )

    # 示例文本
    text = """
    人工智能是计算机科学的一个分支。它旨在创建能够执行通常需要人类智能的任务的系统。

    机器学习是人工智能的一个子领域。它使计算机能够从数据中学习，而无需明确编程。

    深度学习是机器学习的一种方法。它使用多层神经网络来学习数据的复杂表示。

    自然语言处理是人工智能的另一个重要领域。它使计算机能够理解、解释和生成人类语言。
    """

    # 语义分块
    chunks = await chunker.chunk(text, document_id="demo_doc")

    logger.info(f"Created {len(chunks)} semantic chunks:")
    for i, chunk in enumerate(chunks):
        logger.info(f"  Chunk {i}: {len(chunk['content'])} chars")
        logger.info(f"    Preview: {chunk['content'][:50]}...")


async def demo_document_aware_chunking():
    """演示文档类型感知分块"""
    logger.info("\n=== Demo: Document-Aware Chunking ===")

    from app.core.document_aware_chunker import DocumentAwareChunker

    # 初始化
    chunker = DocumentAwareChunker()

    # Markdown 文本
    markdown_text = """
# 第一章 引言

这是第一章的内容。介绍了基本概念。

## 1.1 背景

详细说明项目背景。

## 1.2 目标

列出主要目标。

# 第二章 方法

这是第二章的内容。描述了具体方法。

## 2.1 设计

系统设计说明。
    """

    # Markdown 分块
    chunks = await chunker.chunk(
        text=markdown_text,
        document_id="demo_markdown",
        doc_type="markdown",
    )

    logger.info(f"Created {len(chunks)} markdown chunks:")
    for chunk in chunks:
        metadata = chunk["metadata"]
        logger.info(
            f"  - Level {metadata['header_level']}: {metadata['header_text']} "
            f"({len(chunk['content'])} chars)"
        )


async def demo_context_enhancement():
    """演示上下文增强"""
    logger.info("\n=== Demo: Context Enhancement ===")

    from app.core.context_enhancer import ContextEnhancer
    from app.core.chunker import DocumentChunker

    # 创建基础分块
    chunker = DocumentChunker(chunk_size=200, chunk_overlap=20)
    text = """
    第一段内容。这是关于人工智能的介绍。人工智能改变了我们的生活方式。

    第二段内容。机器学习是AI的核心技术。它通过数据训练模型。

    第三段内容。深度学习取得了突破性进展。神经网络变得越来越强大。

    第四段内容。未来AI将在更多领域发挥作用。我们需要关注AI的伦理问题。
    """

    chunks = await chunker.chunk(text, document_id="demo_doc")

    # 上下文增强
    enhancer = ContextEnhancer(
        include_prev_summary=True,
        include_next_summary=True,
        include_metadata=True,
    )

    document_metadata = {
        "title": "人工智能技术简介",
        "author": "张三",
        "tags": ["AI", "机器学习"],
    }

    enhanced_chunks = await enhancer.enhance_chunks(
        chunks=chunks,
        document_metadata=document_metadata,
    )

    logger.info(f"Enhanced {len(enhanced_chunks)} chunks:")
    for i, chunk in enumerate(enhanced_chunks[:2]):  # 只展示前2个
        logger.info(f"\n  Chunk {i}:")
        logger.info(f"    Original: {chunk['content'][:50]}...")

        if "prev_context" in chunk:
            logger.info(f"    Prev context: {chunk['prev_context'][:50]}...")

        if "next_context" in chunk:
            logger.info(f"    Next context: {chunk['next_context'][:50]}...")

        if "document_metadata" in chunk:
            logger.info(f"    Doc metadata: {chunk['document_metadata']}")


async def demo_chunk_quality_evaluation():
    """演示分块质量评估"""
    logger.info("\n=== Demo: Chunk Quality Evaluation ===")

    from app.core.chunk_quality_evaluator import ChunkQualityEvaluator, ComparativeEvaluator
    from app.core.chunker import DocumentChunker
    from app.core.semantic_chunker import SemanticChunker
    from app.core.embedder import BGE_M3_Embedder

    # 准备文本
    text = """
    人工智能技术正在快速发展。机器学习、深度学习和自然语言处理是其核心领域。

    在医疗领域，AI可以帮助诊断疾病。在金融领域，AI可以进行风险评估。

    然而，我们也需要关注AI的伦理问题。隐私保护、算法偏见等都是重要议题。

    未来，AI将继续改变我们的生活和工作方式。我们需要做好准备迎接这些变化。
    """ * 3  # 重复3次，增加长度

    # 使用不同策略分块
    strategies_results = {}

    # 1. 固定大小分块
    fixed_chunker = DocumentChunker(chunk_size=200, chunk_overlap=20)
    strategies_results["fixed_size"] = await fixed_chunker.chunk(text, "demo_doc")

    # 2. 语义分块
    embedder = BGE_M3_Embedder()
    semantic_chunker = SemanticChunker(embedder=embedder)
    strategies_results["semantic"] = await semantic_chunker.chunk(text, "demo_doc")

    # 评估质量
    evaluator = ChunkQualityEvaluator(min_score=0.7)

    logger.info("Evaluating chunking strategies:")

    for strategy_name, chunks in strategies_results.items():
        evaluation = await evaluator.evaluate(chunks, text)
        logger.info(f"\n  {strategy_name}:")
        logger.info(f"    Overall score: {evaluation['overall_score']:.2f}")
        logger.info(f"    Acceptable: {evaluation['is_acceptable']}")
        logger.info(f"    Chunks: {evaluation['statistics']['total_chunks']}")
        logger.info(f"    Avg size: {evaluation['statistics']['avg_chunk_size']:.0f} chars")

        if evaluation['issues']:
            logger.info(f"    Issues: {evaluation['issues']}")

    # 对比评估
    comparative_evaluator = ComparativeEvaluator(evaluator)
    comparison = await comparative_evaluator.compare_strategies(strategies_results, text)

    logger.info(f"\n  Best strategy: {comparison['best_strategy']} "
                f"(score={comparison['best_score']:.2f})")

    # 生成报告
    report = comparative_evaluator.generate_report(comparison)
    logger.info(f"\n{'='*80}")
    logger.info(report)


async def main():
    """运行所有演示"""
    try:
        # Iter 1: 性能优化
        # await demo_batch_processing()  # 需要真实的文档
        # await demo_streaming_processing()  # 需要真实的大文件
        await demo_task_queue()

        # Iter 2: 智能分块
        await demo_semantic_chunking()
        await demo_document_aware_chunking()
        await demo_context_enhancement()
        await demo_chunk_quality_evaluation()

        logger.info("\n✅ All demos completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
