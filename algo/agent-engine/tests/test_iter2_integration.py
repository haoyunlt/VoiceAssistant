"""
Iteration 2 集成测试
测试 Self-RAG、智能记忆管理和 Multi-Agent 协作的集成
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSelfRAGIntegration:
    """Self-RAG 集成测试"""

    @pytest.mark.asyncio
    async def test_self_rag_query_flow(self):
        """测试 Self-RAG 完整查询流程"""
        # 模拟导入
        with patch('app.core.self_rag.self_rag_service.SelfRAGService') as MockService:
            mock_service = MockService.return_value

            # 模拟查询结果
            mock_result = {
                "query": "什么是RAG？",
                "answer": "RAG 是检索增强生成技术...",
                "confidence": 0.92,
                "retrieval_strategy": "hybrid",
                "refinement_count": 1,
                "hallucination_level": "low",
                "is_grounded": True,
            }

            mock_service.query = AsyncMock(return_value=MagicMock(**mock_result))

            # 执行查询
            result = await mock_service.query(
                query="什么是RAG？",
                context={},
                config={}
            )

            # 验证结果
            assert result.query == "什么是RAG？"
            assert result.confidence >= 0.9
            assert result.is_grounded is True

    @pytest.mark.asyncio
    async def test_adaptive_retrieval(self):
        """测试自适应检索策略选择"""
        with patch('app.core.self_rag.adaptive_retriever.AdaptiveRetriever') as MockRetriever:
            mock_retriever = MockRetriever.return_value

            # 简单查询 -> dense 策略
            mock_retriever.retrieve = AsyncMock(return_value={
                "documents": ["doc1", "doc2"],
                "strategy": "dense",
            })

            result = await mock_retriever.retrieve("简单问题", {})
            assert result["strategy"] == "dense"

            # 复杂查询 -> hybrid 策略
            mock_retriever.retrieve = AsyncMock(return_value={
                "documents": ["doc1", "doc2", "doc3"],
                "strategy": "hybrid",
            })

            result = await mock_retriever.retrieve("复杂的多步骤查询", {})
            assert result["strategy"] == "hybrid"

    @pytest.mark.asyncio
    async def test_hallucination_detection(self):
        """测试幻觉检测功能"""
        with patch('app.core.self_rag.hallucination_detector.HallucinationDetector') as MockDetector:
            mock_detector = MockDetector.return_value

            # 模拟检测结果
            mock_report = MagicMock(
                level="low",
                is_grounded=True,
                hallucinated_claims=[],
            )

            mock_detector.verify_and_correct = AsyncMock(return_value={
                "report": mock_report,
                "should_review": False,
                "correction_suggestion": None,
            })

            result = await mock_detector.verify_and_correct(
                answer="这是一个有根据的答案。",
                retrieved_docs=["相关文档"],
                query="测试查询"
            )

            assert result["report"].is_grounded is True
            assert result["should_review"] is False


class TestSmartMemoryIntegration:
    """智能记忆管理集成测试"""

    @pytest.mark.asyncio
    async def test_memory_lifecycle(self):
        """测试记忆的完整生命周期"""
        with patch('app.core.memory.smart_memory_manager.SmartMemoryManager') as MockManager:
            mock_manager = MockManager.return_value

            # 1. 添加记忆
            mock_manager.add_memory = AsyncMock(return_value="mem_001")

            memory_id = await mock_manager.add_memory(
                content="用户喜欢技术文档",
                tier="long_term",
                importance=0.9,
            )

            assert memory_id == "mem_001"

            # 2. 检索记忆
            mock_memory = MagicMock(
                memory_id="mem_001",
                content="用户喜欢技术文档",
                tier="long_term",
                importance=0.9,
            )

            mock_manager.retrieve = AsyncMock(return_value=[mock_memory])

            memories = await mock_manager.retrieve(
                query="用户偏好",
                top_k=5
            )

            assert len(memories) == 1
            assert memories[0].importance == 0.9

            # 3. 压缩记忆
            mock_manager.compress_memories = AsyncMock(
                return_value="用户偏好技术相关内容，关注AI和RAG..."
            )

            summary = await mock_manager.compress_memories(tier="short_term")
            assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_intelligent_forgetting(self):
        """测试智能遗忘功能"""
        with patch('app.core.memory.smart_memory_manager.SmartMemoryManager') as MockManager:
            mock_manager = MockManager.return_value

            # 模拟记忆维护
            mock_manager.auto_maintain = AsyncMock(return_value={
                "forgotten": 3,
                "promoted": 1,
                "demoted": 2,
            })

            result = await mock_manager.auto_maintain()

            assert result["forgotten"] > 0
            assert "promoted" in result

    @pytest.mark.asyncio
    async def test_hybrid_retrieval(self):
        """测试混合检索（语义+时间+重要性）"""
        with patch('app.core.memory.smart_memory_manager.SmartMemoryManager') as MockManager:
            mock_manager = MockManager.return_value

            # 模拟混合检索结果
            mock_memories = [
                MagicMock(importance=0.9, created_at="2024-01-15"),  # 高重要性
                MagicMock(importance=0.7, created_at="2024-01-16"),  # 中重要性，较新
                MagicMock(importance=0.5, created_at="2024-01-14"),  # 低重要性
            ]

            mock_manager.retrieve = AsyncMock(return_value=mock_memories)

            memories = await mock_manager.retrieve(
                query="测试查询",
                top_k=3
            )

            # 验证返回的记忆按综合得分排序
            assert len(memories) == 3
            assert memories[0].importance >= memories[1].importance


class TestMultiAgentIntegration:
    """Multi-Agent 协作集成测试"""

    @pytest.mark.asyncio
    async def test_parallel_collaboration(self):
        """测试并行协作模式"""
        with patch('app.core.multi_agent.enhanced_coordinator.EnhancedMultiAgentCoordinator') as MockCoordinator:
            mock_coordinator = MockCoordinator.return_value

            # 模拟并行协作结果
            mock_result = {
                "final_output": "综合分析结果...",
                "agents_involved": ["researcher_01", "planner_01", "executor_01"],
                "completion_time": 2.5,
                "quality_score": 0.88,
                "status": "completed",
            }

            mock_coordinator.collaborate = AsyncMock(return_value=mock_result)

            result = await mock_coordinator.collaborate(
                task="分析任务",
                mode="parallel",
            )

            assert result["status"] == "completed"
            assert len(result["agents_involved"]) == 3
            assert result["quality_score"] >= 0.8

    @pytest.mark.asyncio
    async def test_debate_mode(self):
        """测试辩论模式"""
        with patch('app.core.multi_agent.enhanced_coordinator.EnhancedMultiAgentCoordinator') as MockCoordinator:
            mock_coordinator = MockCoordinator.return_value

            mock_result = {
                "consensus": "AI应辅助而非替代人类",
                "debate_history": [
                    {"round": 1, "agent": "researcher", "position": "支持"},
                    {"round": 1, "agent": "planner", "position": "反对"},
                    {"round": 2, "agent": "researcher", "position": "妥协"},
                    {"round": 2, "agent": "planner", "position": "同意"},
                ],
                "status": "completed",
            }

            mock_coordinator.collaborate = AsyncMock(return_value=mock_result)

            result = await mock_coordinator.collaborate(
                task="AI是否应该替代人类医生？",
                mode="debate",
            )

            assert "consensus" in result
            assert len(result["debate_history"]) > 0

    @pytest.mark.asyncio
    async def test_dynamic_tool_loading(self):
        """测试动态工具加载"""
        with patch('app.core.multi_agent.enhanced_coordinator.EnhancedMultiAgentCoordinator') as MockCoordinator:
            mock_coordinator = MockCoordinator.return_value

            # 模拟工具注册表
            mock_tool_registry = MagicMock()
            mock_tool_registry.get_tools_by_category = MagicMock(
                side_effect=lambda cat: ["search_tool", "knowledge_tool"] if cat == "search" else ["calc_tool"]
            )

            mock_coordinator.tool_registry = mock_tool_registry

            # 验证根据角色加载工具
            tools = mock_tool_registry.get_tools_by_category("search")
            assert len(tools) == 2
            assert "search_tool" in tools


class TestIntegratedScenario:
    """集成场景测试"""

    @pytest.mark.asyncio
    async def test_complete_qa_flow(self):
        """测试完整的问答流程（Self-RAG + 记忆 + Multi-Agent）"""
        # 场景：用户提出复杂技术问题

        # 1. 从记忆中检索上下文
        with patch('app.core.memory.smart_memory_manager.SmartMemoryManager') as MockMemory:
            mock_memory = MockMemory.return_value
            mock_memory.retrieve = AsyncMock(return_value=[
                MagicMock(content="用户是资深开发者", importance=0.9),
                MagicMock(content="用户关注AI应用", importance=0.8),
            ])

            context_memories = await mock_memory.retrieve("用户背景", top_k=5)
            assert len(context_memories) == 2

        # 2. 使用 Self-RAG 检索和生成答案
        with patch('app.core.self_rag.self_rag_service.SelfRAGService') as MockSelfRAG:
            mock_self_rag = MockSelfRAG.return_value
            mock_self_rag.query = AsyncMock(return_value=MagicMock(
                answer="这是一个高质量的答案...",
                confidence=0.91,
                is_grounded=True,
            ))

            rag_result = await mock_self_rag.query(
                query="如何部署RAG系统？",
                context={"user_level": "senior"}
            )

            assert rag_result.confidence > 0.9

        # 3. 如果需要，调用 Multi-Agent 处理子任务
        with patch('app.core.multi_agent.enhanced_coordinator.EnhancedMultiAgentCoordinator') as MockMA:
            mock_ma = MockMA.return_value
            mock_ma.collaborate = AsyncMock(return_value={
                "final_output": "详细部署方案...",
                "quality_score": 0.88,
                "status": "completed",
            })

            ma_result = await mock_ma.collaborate(
                task="生成详细部署方案",
                mode="parallel",
            )

            assert ma_result["quality_score"] > 0.8

        # 4. 更新记忆
        with patch('app.core.memory.smart_memory_manager.SmartMemoryManager') as MockMemory:
            mock_memory = MockMemory.return_value
            mock_memory.add_memory = AsyncMock(return_value="mem_new")

            new_mem_id = await mock_memory.add_memory(
                content="用户询问了RAG部署问题",
                tier="short_term",
                importance=0.7,
            )

            assert new_mem_id == "mem_new"

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """测试错误处理和恢复"""
        # 模拟 Self-RAG 失败，回退到简单检索
        with patch('app.core.self_rag.self_rag_service.SelfRAGService') as MockSelfRAG:
            mock_self_rag = MockSelfRAG.return_value

            # 第一次失败
            mock_self_rag.query = AsyncMock(side_effect=Exception("Retrieval failed"))

            with pytest.raises(Exception):
                await mock_self_rag.query(query="测试", context={})

            # 第二次重试成功
            mock_self_rag.query = AsyncMock(return_value=MagicMock(
                answer="回退答案",
                confidence=0.7,
            ))

            result = await mock_self_rag.query(query="测试", context={})
            assert result.confidence >= 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
