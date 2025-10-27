# 算法服务迭代计划 (Algo Services Roadmap)

> **版本**: v2.0  
> **更新时间**: 2025-10-27  
> **服务类型**: Python算法服务  
> **技术栈**: Python 3.11+, FastAPI, AsyncIO

## 📋 目录

- [1. Agent Engine - AI代理执行引擎](#1-agent-engine)
- [2. Voice Engine - 语音处理引擎](#2-voice-engine)
- [3. RAG Engine - 检索增强生成](#3-rag-engine)
- [4. Retrieval Service - 混合检索服务](#4-retrieval-service)
- [5. Model Adapter - 模型适配器](#5-model-adapter)
- [6. Indexing Service - 索引服务](#6-indexing-service)
- [7. Multimodal Engine - 多模态引擎](#7-multimodal-engine)
- [8. Knowledge Service - 知识图谱服务](#8-knowledge-service)
- [9. Vector Store Adapter - 向量数据库适配器](#9-vector-store-adapter)

---

## 1. Agent Engine

### 1.1 当前功能清单

#### ✅ 已实现功能

| 功能模块 | 功能描述 | 完成度 | 代码位置 |
|---------|---------|--------|----------|
| **ReAct执行器** | Reasoning+Acting循环执行 | 100% | `app/core/executor/react_executor.py` |
| **Plan-Execute执行器** | 计划-执行两阶段Agent | 100% | `app/executors/plan_execute_executor.py` |
| **Reflexion执行器** | 自我反思与修正 | 90% | `app/executors/reflexion_executor.py` |
| **工具注册表** | 动态工具注册与管理 | 100% | `app/tools/tool_registry.py` |
| **记忆管理器** | 对话记忆持久化 | 80% | `app/memory/memory_manager.py` |
| **LLM客户端** | 多提供商LLM调用 | 100% | `app/infrastructure/llm_client.py` |
| **WebSocket支持** | 实时双向通信 | 100% | `app/routers/websocket.py` |
| **任务管理器** | 异步任务状态追踪 | 100% | `app/services/task_manager.py` |
| **RBAC权限控制** | 基于角色的访问控制 | 90% | `app/auth/rbac.py` |

#### 🔄 部分完成功能

| 功能 | 当前状态 | 缺失部分 | 优先级 |
|------|---------|----------|--------|
| **Multi-Agent协作** | 60% | 代理间通信协议、冲突解决 | P0 |
| **工具市场** | 40% | 插件沙箱、审核机制 | P1 |
| **向量记忆** | 50% | 长期记忆检索、遗忘机制 | P1 |
| **流式执行** | 70% | 事件标准化、错误恢复 | P1 |

### 1.2 业界对标分析

#### 对标项目: LangChain/LangGraph/AutoGPT

| 功能特性 | LangChain | AutoGPT | **Agent Engine** | 差距分析 |
|---------|-----------|---------|------------------|---------|
| ReAct模式 | ✅ | ✅ | ✅ | 对标一致 |
| Multi-Agent | ✅ (LangGraph) | ❌ | 🔄 60% | 需要完善通信协议 |
| 工具调用 | ✅ | ✅ | ✅ | 对标一致 |
| Self-Reflection | ✅ (Reflexion) | ✅ | 🔄 90% | 需要优化错误恢复 |
| 长期记忆 | ✅ (Mem0) | ✅ | 🔄 50% | 需要向量记忆检索 |
| 工作流编排 | ✅ (LangGraph) | ❌ | 🔄 40% | 需要DAG执行引擎 |
| 流式输出 | ✅ | ❌ | 🔄 70% | 需要标准化事件流 |

#### 核心差距

1. **Multi-Agent协作能力不足**: 缺少Agent间消息传递、任务分配、冲突解决机制
2. **工作流编排缺失**: 无法支持复杂的DAG工作流
3. **长期记忆检索弱**: 向量记忆检索效率低，缺少遗忘机制

### 1.3 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 1.3.1 Multi-Agent协作框架

**功能描述**: 实现多个Agent协同完成复杂任务

**设计方案**:

```python
# app/core/multi_agent/coordinator.py

from typing import List, Dict, Any
from enum import Enum
import asyncio

class AgentRole(Enum):
    """Agent角色定义"""
    COORDINATOR = "coordinator"  # 协调者
    RESEARCHER = "researcher"    # 研究员
    PLANNER = "planner"          # 规划者
    EXECUTOR = "executor"        # 执行者
    REVIEWER = "reviewer"        # 审核者

class Message:
    """Agent间消息"""
    def __init__(
        self,
        sender: str,
        receiver: str,
        content: str,
        message_type: str = "text",
        priority: int = 0,
        metadata: Dict = None
    ):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.priority = priority
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

class Agent:
    """基础Agent类"""
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        llm_client: LLMClient,
        tools: List[Tool] = None
    ):
        self.agent_id = agent_id
        self.role = role
        self.llm_client = llm_client
        self.tools = tools or []
        self.message_queue = asyncio.Queue()
        
    async def process_message(self, message: Message) -> Message:
        """处理接收到的消息"""
        # 1. 理解消息
        understanding = await self.llm_client.analyze(message.content)
        
        # 2. 决策行动
        if self.role == AgentRole.RESEARCHER:
            response = await self._research(understanding)
        elif self.role == AgentRole.PLANNER:
            response = await self._plan(understanding)
        elif self.role == AgentRole.EXECUTOR:
            response = await self._execute(understanding)
        else:
            response = await self._coordinate(understanding)
            
        # 3. 生成回复消息
        return Message(
            sender=self.agent_id,
            receiver=message.sender,
            content=response,
            metadata={"in_reply_to": message.timestamp}
        )
        
    async def _research(self, query: str) -> str:
        """研究员角色: 搜索和分析信息"""
        # 调用搜索工具
        search_results = await self.tools["search"].execute(query)
        # 分析结果
        analysis = await self.llm_client.analyze(search_results)
        return analysis

class MultiAgentCoordinator:
    """多Agent协调器"""
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.message_bus = asyncio.Queue()
        self.task_queue = asyncio.Queue()
        
    def register_agent(self, agent: Agent):
        """注册Agent"""
        self.agents[agent.agent_id] = agent
        
    async def execute_collaborative_task(
        self,
        task: str,
        agents: List[str]
    ) -> Dict[str, Any]:
        """协同执行任务"""
        # 1. 任务分解
        coordinator = self.agents.get("coordinator")
        subtasks = await coordinator.decompose_task(task, agents)
        
        # 2. 分配给各个Agent
        results = {}
        for agent_id, subtask in subtasks.items():
            message = Message(
                sender="coordinator",
                receiver=agent_id,
                content=subtask,
                message_type="task"
            )
            await self.agents[agent_id].message_queue.put(message)
            
        # 3. 收集结果
        for agent_id in agents:
            response = await self._wait_for_response(agent_id)
            results[agent_id] = response
            
        # 4. 结果融合
        final_result = await coordinator.merge_results(results)
        
        return {
            "task": task,
            "subtask_results": results,
            "final_result": final_result,
            "agents_involved": agents
        }
        
    async def resolve_conflict(
        self,
        agent1_id: str,
        agent2_id: str,
        conflict: str
    ) -> str:
        """冲突解决"""
        # 使用协调者或投票机制解决冲突
        coordinator = self.agents.get("coordinator")
        resolution = await coordinator.resolve(conflict)
        return resolution
```

**实现步骤**:

1. Week 1-2: 实现基础Agent类和消息传递机制
2. Week 3-4: 实现协调器和任务分配逻辑
3. Week 5-6: 实现冲突解决和结果融合
4. Week 7-8: 测试和优化

**验收标准**:

- [ ] 支持3个以上Agent协同工作
- [ ] 消息传递延迟<100ms
- [ ] 冲突解决成功率>90%
- [ ] 任务分解准确率>85%

##### 1.3.2 Self-RAG集成

**功能描述**: Agent根据检索质量自适应决定是否使用RAG

**设计方案**:

```python
# app/core/self_rag/adaptive_retriever.py

from enum import Enum

class RetrievalDecision(Enum):
    """检索决策"""
    RETRIEVE = "retrieve"          # 需要检索
    NO_RETRIEVE = "no_retrieve"    # 不需要检索
    ITERATIVE = "iterative"        # 迭代检索

class RelevanceLevel(Enum):
    """相关性等级"""
    HIGHLY_RELEVANT = "highly_relevant"
    RELEVANT = "relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    IRRELEVANT = "irrelevant"

class SelfRAGAgent:
    """Self-RAG Agent"""
    
    def __init__(
        self,
        llm_client: LLMClient,
        retrieval_client: RetrievalClient,
        threshold_confidence: float = 0.8
    ):
        self.llm_client = llm_client
        self.retrieval_client = retrieval_client
        self.threshold_confidence = threshold_confidence
        
    async def decide_retrieval(self, query: str) -> RetrievalDecision:
        """决策是否需要检索"""
        prompt = f"""
        Analyze if external knowledge retrieval is needed for this query:
        
        Query: {query}
        
        Return one of:
        - RETRIEVE: if external knowledge is necessary
        - NO_RETRIEVE: if you have sufficient internal knowledge
        - ITERATIVE: if you need multiple retrieval iterations
        
        Decision:
        """
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a decision assistant"},
            {"role": "user", "content": prompt}
        ])
        
        decision_text = response["content"].strip().upper()
        return RetrievalDecision[decision_text]
        
    async def assess_relevance(
        self,
        query: str,
        chunks: List[Dict]
    ) -> List[Tuple[Dict, RelevanceLevel]]:
        """评估检索结果相关性"""
        assessed = []
        
        for chunk in chunks:
            prompt = f"""
            Query: {query}
            Retrieved Content: {chunk['content']}
            
            Rate relevance (HIGHLY_RELEVANT/RELEVANT/PARTIALLY_RELEVANT/IRRELEVANT):
            """
            
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            level_text = response["content"].strip().upper()
            level = RelevanceLevel[level_text]
            assessed.append((chunk, level))
            
        return assessed
        
    async def generate_with_critique(
        self,
        query: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """生成答案并进行自我批判"""
        # 1. 生成初始答案
        context = "\n\n".join([c["content"] for c in chunks])
        answer = await self.llm_client.chat([
            {"role": "system", "content": "Answer based on context"},
            {"role": "user", "content": f"Context:\n{context}\n\nQuery: {query}"}
        ])
        
        # 2. 自我批判
        critique_prompt = f"""
        Query: {query}
        Generated Answer: {answer['content']}
        Context: {context}
        
        Critique the answer on:
        1. Factual accuracy
        2. Relevance to query
        3. Use of context
        4. Completeness
        
        Score (0-1) and explain:
        """
        
        critique = await self.llm_client.chat([
            {"role": "user", "content": critique_prompt}
        ])
        
        # 3. 解析分数
        score = self._parse_score(critique["content"])
        
        # 4. 如果分数低,迭代改进
        if score < self.threshold_confidence:
            answer = await self._refine_answer(query, chunks, critique["content"])
            
        return {
            "answer": answer["content"],
            "confidence": score,
            "critique": critique["content"],
            "iterations": 1 if score >= self.threshold_confidence else 2
        }
        
    async def execute_self_rag(self, query: str) -> Dict[str, Any]:
        """完整的Self-RAG执行流程"""
        # 1. 决策是否检索
        decision = await self.decide_retrieval(query)
        
        if decision == RetrievalDecision.NO_RETRIEVE:
            # 直接生成答案
            answer = await self.llm_client.chat([
                {"role": "user", "content": query}
            ])
            return {
                "answer": answer["content"],
                "used_retrieval": False,
                "confidence": 1.0
            }
            
        # 2. 执行检索
        chunks = await self.retrieval_client.retrieve(query, top_k=10)
        
        # 3. 评估相关性
        assessed_chunks = await self.assess_relevance(query, chunks)
        
        # 4. 过滤相关内容
        relevant_chunks = [
            chunk for chunk, level in assessed_chunks
            if level in [RelevanceLevel.HIGHLY_RELEVANT, RelevanceLevel.RELEVANT]
        ]
        
        if not relevant_chunks:
            # 检索无效,直接生成
            answer = await self.llm_client.chat([
                {"role": "user", "content": query}
            ])
            return {
                "answer": answer["content"],
                "used_retrieval": True,
                "retrieval_effective": False,
                "confidence": 0.5
            }
            
        # 5. 生成并批判
        result = await self.generate_with_critique(query, relevant_chunks)
        
        # 6. 如果是迭代模式且置信度低,再次检索
        if decision == RetrievalDecision.ITERATIVE and result["confidence"] < 0.8:
            # 根据批判结果重新构建查询
            refined_query = await self._refine_query(query, result["critique"])
            chunks = await self.retrieval_client.retrieve(refined_query, top_k=10)
            result = await self.generate_with_critique(refined_query, chunks)
            
        return {
            **result,
            "used_retrieval": True,
            "retrieval_effective": True,
            "chunks_used": len(relevant_chunks)
        }
```

**实现步骤**:

1. Week 1-2: 实现检索决策机制
2. Week 3-4: 实现相关性评估
3. Week 5-6: 实现自我批判和迭代改进
4. Week 7-8: 集成测试和调优

**验收标准**:

- [ ] 检索决策准确率>85%
- [ ] 相关性评估准确率>80%
- [ ] Self-RAG整体准确率相比基线提升>15%
- [ ] 端到端延迟<3s

##### 1.3.3 工具市场与动态加载

**功能描述**: 支持第三方工具插件动态注册和安全执行

**设计方案**:

```python
# app/tools/tool_marketplace.py

import importlib
import inspect
from typing import Callable, Dict, Any
from pydantic import BaseModel, validator
import hashlib
import json

class ToolMetadata(BaseModel):
    """工具元数据"""
    name: str
    version: str
    author: str
    description: str
    category: str  # search/computation/integration/...
    tags: List[str]
    requires_auth: bool = False
    parameters: Dict[str, Any]
    examples: List[Dict]
    
class ToolPermissions(BaseModel):
    """工具权限"""
    network_access: bool = False
    file_system_access: bool = False
    database_access: bool = False
    max_execution_time: int = 30  # seconds
    max_memory_mb: int = 512

class ToolSandbox:
    """工具沙箱"""
    
    def __init__(self, permissions: ToolPermissions):
        self.permissions = permissions
        
    async def execute_safe(
        self,
        tool_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """在沙箱中安全执行工具"""
        import resource
        import signal
        
        # 设置资源限制
        def set_limits():
            # 内存限制
            mem_limit = self.permissions.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
            
            # 时间限制
            signal.alarm(self.permissions.max_execution_time)
            
        try:
            # 在子进程中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_with_limits,
                tool_func,
                set_limits,
                args,
                kwargs
            )
            return result
            
        except MemoryError:
            raise ToolExecutionError("Tool exceeded memory limit")
        except TimeoutError:
            raise ToolExecutionError("Tool exceeded time limit")
        except Exception as e:
            raise ToolExecutionError(f"Tool execution failed: {str(e)}")
            
    def _execute_with_limits(
        self,
        func: Callable,
        set_limits_func: Callable,
        args: tuple,
        kwargs: dict
    ):
        """执行函数并设置限制"""
        set_limits_func()
        return func(*args, **kwargs)

class ToolMarketplace:
    """工具市场"""
    
    def __init__(self, registry_path: str = "./tool_registry"):
        self.registry_path = registry_path
        self.tools: Dict[str, Dict] = {}
        self.load_registry()
        
    def load_registry(self):
        """加载工具注册表"""
        registry_file = f"{self.registry_path}/registry.json"
        if os.path.exists(registry_file):
            with open(registry_file, 'r') as f:
                self.tools = json.load(f)
                
    def register_tool(
        self,
        tool_func: Callable,
        metadata: ToolMetadata,
        permissions: ToolPermissions
    ) -> str:
        """注册新工具"""
        # 1. 验证工具函数签名
        sig = inspect.signature(tool_func)
        self._validate_signature(sig, metadata.parameters)
        
        # 2. 生成工具ID
        tool_id = self._generate_tool_id(metadata)
        
        # 3. 安全检查
        if not self._security_check(tool_func, permissions):
            raise SecurityError("Tool failed security check")
            
        # 4. 保存工具
        tool_info = {
            "id": tool_id,
            "metadata": metadata.dict(),
            "permissions": permissions.dict(),
            "function_path": f"{tool_func.__module__}.{tool_func.__name__}",
            "checksum": self._calculate_checksum(tool_func),
            "registered_at": datetime.utcnow().isoformat()
        }
        
        self.tools[tool_id] = tool_info
        self._save_registry()
        
        logger.info(f"Tool registered: {metadata.name} ({tool_id})")
        return tool_id
        
    async def execute_tool(
        self,
        tool_id: str,
        inputs: Dict[str, Any],
        user_id: str = None
    ) -> Any:
        """执行工具"""
        # 1. 获取工具信息
        tool_info = self.tools.get(tool_id)
        if not tool_info:
            raise ToolNotFoundError(f"Tool {tool_id} not found")
            
        # 2. 权限检查
        if tool_info["metadata"]["requires_auth"] and not user_id:
            raise AuthenticationError("Tool requires authentication")
            
        # 3. 加载工具函数
        tool_func = self._load_tool_function(tool_info["function_path"])
        
        # 4. 验证校验和
        current_checksum = self._calculate_checksum(tool_func)
        if current_checksum != tool_info["checksum"]:
            raise SecurityError("Tool checksum mismatch")
            
        # 5. 在沙箱中执行
        sandbox = ToolSandbox(ToolPermissions(**tool_info["permissions"]))
        result = await sandbox.execute_safe(tool_func, **inputs)
        
        return result
        
    def search_tools(
        self,
        query: str = None,
        category: str = None,
        tags: List[str] = None
    ) -> List[Dict]:
        """搜索工具"""
        results = []
        
        for tool_id, tool_info in self.tools.items():
            metadata = tool_info["metadata"]
            
            # 分类过滤
            if category and metadata["category"] != category:
                continue
                
            # 标签过滤
            if tags and not set(tags).intersection(set(metadata["tags"])):
                continue
                
            # 关键词搜索
            if query:
                searchable = f"{metadata['name']} {metadata['description']}".lower()
                if query.lower() not in searchable:
                    continue
                    
            results.append({
                "id": tool_id,
                "name": metadata["name"],
                "description": metadata["description"],
                "category": metadata["category"],
                "author": metadata["author"],
                "version": metadata["version"]
            })
            
        return results
        
    def _validate_signature(self, sig: inspect.Signature, params: Dict):
        """验证函数签名与参数定义匹配"""
        sig_params = set(sig.parameters.keys())
        declared_params = set(params.keys())
        
        if sig_params != declared_params:
            raise ValueError(f"Parameter mismatch: {sig_params} vs {declared_params}")
            
    def _security_check(self, func: Callable, permissions: ToolPermissions) -> bool:
        """安全检查"""
        import ast
        
        # 获取函数源代码
        source = inspect.getsource(func)
        tree = ast.parse(source)
        
        # 检查危险操作
        for node in ast.walk(tree):
            # 检查文件系统访问
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'id'):
                    func_name = node.func.id
                    if func_name in ['open', 'write', 'remove'] and not permissions.file_system_access:
                        logger.warning(f"Tool uses file system without permission")
                        return False
                        
            # 检查网络访问
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                module = node.names[0].name if isinstance(node, ast.Import) else node.module
                if module in ['requests', 'urllib', 'socket'] and not permissions.network_access:
                    logger.warning(f"Tool uses network without permission")
                    return False
                    
        return True
        
    def _generate_tool_id(self, metadata: ToolMetadata) -> str:
        """生成工具ID"""
        content = f"{metadata.name}{metadata.version}{metadata.author}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def _calculate_checksum(self, func: Callable) -> str:
        """计算函数校验和"""
        source = inspect.getsource(func)
        return hashlib.sha256(source.encode()).hexdigest()
        
    def _load_tool_function(self, function_path: str) -> Callable:
        """动态加载工具函数"""
        module_path, func_name = function_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
        
    def _save_registry(self):
        """保存注册表"""
        registry_file = f"{self.registry_path}/registry.json"
        os.makedirs(self.registry_path, exist_ok=True)
        with open(registry_file, 'w') as f:
            json.dump(self.tools, f, indent=2)
```

**使用示例**:

```python
# 示例1: 注册自定义工具
def weather_lookup(city: str, country: str = "US") -> Dict:
    """查询天气"""
    import requests
    api_key = os.getenv("WEATHER_API_KEY")
    url = f"https://api.weather.com/v1/{city}?country={country}&key={api_key}"
    response = requests.get(url)
    return response.json()

marketplace = ToolMarketplace()

tool_id = marketplace.register_tool(
    tool_func=weather_lookup,
    metadata=ToolMetadata(
        name="weather_lookup",
        version="1.0.0",
        author="john@example.com",
        description="Get current weather for a city",
        category="integration",
        tags=["weather", "api", "data"],
        requires_auth=True,
        parameters={
            "city": {"type": "string", "required": True},
            "country": {"type": "string", "required": False, "default": "US"}
        },
        examples=[
            {"input": {"city": "London", "country": "UK"}, "output": {"temp": 15, "condition": "Cloudy"}}
        ]
    ),
    permissions=ToolPermissions(
        network_access=True,
        file_system_access=False,
        max_execution_time=10,
        max_memory_mb=256
    )
)

# 示例2: 执行工具
result = await marketplace.execute_tool(
    tool_id=tool_id,
    inputs={"city": "Beijing", "country": "CN"},
    user_id="user_123"
)

# 示例3: 搜索工具
weather_tools = marketplace.search_tools(
    query="weather",
    category="integration"
)
```

**实现步骤**:

1. Week 1-2: 实现工具注册和元数据管理
2. Week 3-4: 实现沙箱执行环境
3. Week 5-6: 实现安全检查和权限控制
4. Week 7-8: 实现工具市场API和测试

**验收标准**:

- [ ] 支持20+工具注册
- [ ] 沙箱安全性通过渗透测试
- [ ] 工具执行成功率>95%
- [ ] 动态加载延迟<500ms

#### 🎯 P1 任务 (Q3 2025)

##### 1.3.4 DAG工作流编排

**功能描述**: 支持复杂的有向无环图(DAG)工作流编排

**核心设计**:

```python
# app/workflows/dag_executor.py

from typing import List, Dict, Callable, Any
from dataclasses import dataclass
from enum import Enum

class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowNode:
    """工作流节点"""
    node_id: str
    node_type: str  # agent/tool/condition/merge
    config: Dict[str, Any]
    dependencies: List[str]  # 依赖的节点ID
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: str = None

class DAGWorkflow:
    """DAG工作流"""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[Tuple[str, str]] = []
        
    def add_node(self, node: WorkflowNode):
        """添加节点"""
        self.nodes[node.node_id] = node
        
    def add_edge(self, from_node: str, to_node: str):
        """添加边"""
        self.edges.append((from_node, to_node))
        self.nodes[to_node].dependencies.append(from_node)
        
    def validate(self) -> bool:
        """验证DAG有效性(无环)"""
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # 检查所有邻居
            neighbors = [to_node for from_node, to_node in self.edges if from_node == node_id]
            for neighbor in neighbors:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
                    
            rec_stack.remove(node_id)
            return False
            
        for node_id in self.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    return False
        return True

class DAGExecutor:
    """DAG执行器"""
    
    async def execute(self, workflow: DAGWorkflow) -> Dict[str, Any]:
        """执行DAG工作流"""
        # 1. 验证DAG
        if not workflow.validate():
            raise ValueError("Workflow contains cycles")
            
        # 2. 拓扑排序
        execution_order = self._topological_sort(workflow)
        
        # 3. 按序执行
        results = {}
        for node_id in execution_order:
            node = workflow.nodes[node_id]
            
            # 检查依赖是否完成
            if not self._dependencies_met(node, workflow):
                node.status = NodeStatus.SKIPPED
                continue
                
            # 执行节点
            try:
                node.status = NodeStatus.RUNNING
                result = await self._execute_node(node, results)
                node.result = result
                node.status = NodeStatus.COMPLETED
                results[node_id] = result
            except Exception as e:
                node.status = NodeStatus.FAILED
                node.error = str(e)
                logger.error(f"Node {node_id} failed: {e}")
                
        return {
            "workflow_id": workflow.workflow_id,
            "results": results,
            "status": self._compute_final_status(workflow)
        }
        
    def _topological_sort(self, workflow: DAGWorkflow) -> List[str]:
        """拓扑排序"""
        in_degree = {node_id: 0 for node_id in workflow.nodes}
        
        # 计算入度
        for from_node, to_node in workflow.edges:
            in_degree[to_node] += 1
            
        # BFS
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            # 减少邻居入度
            for from_node, to_node in workflow.edges:
                if from_node == node_id:
                    in_degree[to_node] -= 1
                    if in_degree[to_node] == 0:
                        queue.append(to_node)
                        
        return result
```

**实现优先级**: P1  
**预计工作量**: 6周  
**负责人**: 算法工程师

---

## 2. Voice Engine

### 2.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 | 性能指标 |
|------|------|--------|----------|
| **ASR (Whisper)** | 基于Faster-Whisper的语音识别 | 100% | P95延迟~1.5s |
| **TTS (Edge TTS)** | 微软Edge TTS语音合成 | 100% | TTFB~800ms |
| **VAD** | Silero VAD语音活动检测 | 100% | 检测延迟<100ms |
| **Azure备份** | Azure Speech SDK集成 | 90% | 延迟略高 |
| **多语言** | 中英文支持 | 100% | - |
| **音色管理** | 多种中英文音色 | 100% | 30+音色 |
| **流式ASR** | WebSocket实时识别 | 80% | 存在断句问题 |
| **TTS缓存** | 相同文本复用 | 100% | 命中率~60% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **实时全双工** | 同时输入输出、打断处理 | P0 |
| **情感TTS** | 情感标注、韵律控制 | P0 |
| **降噪增强** | 音频预处理、回声消除 | P1 |
| **说话人识别** | 多人对话场景 | P1 |
| **音频编解码优化** | Opus/AAC低延迟编码 | P1 |

### 2.2 业界对标

#### 对标项目: Baichuan-Audio, SpeechBrain

| 功能 | Baichuan-Audio | SpeechBrain | **Voice Engine** | 差距 |
|------|---------------|-------------|------------------|-----|
| 实时ASR | ✅ <500ms | ✅ | 🔄 ~1.5s | 需要优化流式处理 |
| 情感TTS | ✅ | ✅ | ❌ | 缺少情感控制 |
| 全双工 | ✅ | ❌ | ❌ | 需要实现 |
| VAD | ✅ | ✅ | ✅ | 对标一致 |
| 多模态 | ✅ | ❌ | ❌ | 未来规划 |

### 2.3 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 2.3.1 实时全双工语音对话

**目标延迟**: 端到端<1s

**核心优化**:

```python
# app/services/realtime_voice_service.py

import asyncio
from collections import deque

class RealtimeVoiceService:
    """实时全双工语音服务"""
    
    def __init__(
        self,
        asr_service,
        tts_service,
        vad_service,
        buffer_size_ms: int = 200
    ):
        self.asr_service = asr_service
        self.tts_service = tts_service
        self.vad_service = vad_service
        self.buffer_size_ms = buffer_size_ms
        
        # 音频缓冲区
        self.input_buffer = deque(maxlen=100)
        self.output_buffer = deque(maxlen=100)
        
        # 状态
        self.is_speaking = False
        self.is_listening = True
        
    async def start_duplex_conversation(
        self,
        input_stream: AsyncIterator[bytes],
        output_stream: AsyncIterator[bytes]
    ):
        """启动全双工对话"""
        # 并行运行输入和输出
        await asyncio.gather(
            self._process_input(input_stream),
            self._process_output(output_stream),
            self._handle_interruptions()
        )
        
    async def _process_input(self, stream: AsyncIterator[bytes]):
        """处理输入音频流"""
        async for audio_chunk in stream:
            # 1. VAD检测
            is_speech = await self.vad_service.detect(audio_chunk)
            
            if is_speech:
                self.input_buffer.append(audio_chunk)
                
                # 2. 累积到足够长度后识别
                if len(self.input_buffer) * 20 >= self.buffer_size_ms:  # 假设每chunk 20ms
                    audio_segment = b''.join(self.input_buffer)
                    self.input_buffer.clear()
                    
                    # 3. 流式ASR
                    text = await self.asr_service.recognize_streaming(audio_segment)
                    
                    if text:
                        # 4. 触发响应生成
                        await self._generate_response(text)
                        
    async def _process_output(self, stream: AsyncIterator[bytes]):
        """处理输出音频流"""
        while True:
            if self.output_buffer:
                audio_chunk = self.output_buffer.popleft()
                await stream.send(audio_chunk)
            else:
                await asyncio.sleep(0.01)
                
    async def _generate_response(self, user_input: str):
        """生成响应"""
        # 1. LLM生成文本响应
        response_text = await self.llm_client.chat([
            {"role": "user", "content": user_input}
        ])
        
        # 2. 流式TTS合成
        async for audio_chunk in self.tts_service.synthesize_stream(response_text):
            self.output_buffer.append(audio_chunk)
            
    async def _handle_interruptions(self):
        """处理打断"""
        while True:
            # 如果检测到用户说话且系统正在播放,清空输出缓冲区
            if self.is_listening and self.is_speaking:
                self.output_buffer.clear()
                self.is_speaking = False
                
            await asyncio.sleep(0.05)
```

**实现步骤**:
1. Week 1-2: 优化流式ASR延迟
2. Week 3-4: 实现流式TTS首字节优化
3. Week 5-6: 实现全双工通信协议
4. Week 7-8: 测试和调优

**验收标准**:
- [ ] ASR P95延迟<500ms
- [ ] TTS TTFB<300ms
- [ ] 端到端对话延迟<1s
- [ ] 打断响应<200ms

##### 2.3.2 情感化TTS

**功能描述**: 根据文本情感自动调整语音韵律

**设计方案**:

```python
# app/services/emotional_tts_service.py

from enum import Enum

class Emotion(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    GENTLE = "gentle"

class EmotionalTTSService:
    """情感化TTS服务"""
    
    async def synthesize_with_emotion(
        self,
        text: str,
        emotion: Emotion = Emotion.NEUTRAL,
        intensity: float = 0.5
    ) -> bytes:
        """合成情感语音"""
        # 1. 情感分析(如果未指定)
        if emotion == Emotion.NEUTRAL:
            emotion = await self._detect_emotion(text)
            
        # 2. 生成SSML with emotion
        ssml = self._generate_emotional_ssml(text, emotion, intensity)
        
        # 3. 合成
        audio = await self.tts_service.synthesize_ssml(ssml)
        return audio
        
    def _generate_emotional_ssml(
        self,
        text: str,
        emotion: Emotion,
        intensity: float
    ) -> str:
        """生成情感SSML"""
        # 根据情感调整参数
        params = self._get_emotion_parameters(emotion, intensity)
        
        ssml = f"""
        <speak version='1.0' xml:lang='zh-CN'>
            <voice name='zh-CN-XiaoxiaoNeural'>
                <prosody rate='{params["rate"]}' pitch='{params["pitch"]}' volume='{params["volume"]}'>
                    <mstts:express-as style='{params["style"]}' styledegree='{intensity}'>
                        {text}
                    </mstts:express-as>
                </prosody>
            </voice>
        </speak>
        """
        return ssml
        
    def _get_emotion_parameters(self, emotion: Emotion, intensity: float) -> Dict:
        """获取情感参数"""
        params_map = {
            Emotion.HAPPY: {
                "rate": "+10%",
                "pitch": "+5Hz",
                "volume": "+10%",
                "style": "cheerful"
            },
            Emotion.SAD: {
                "rate": "-10%",
                "pitch": "-5Hz",
                "volume": "-5%",
                "style": "sad"
            },
            Emotion.ANGRY: {
                "rate": "+5%",
                "pitch": "+10Hz",
                "volume": "+15%",
                "style": "angry"
            },
            Emotion.GENTLE: {
                "rate": "-5%",
                "pitch": "+0Hz",
                "volume": "+0%",
                "style": "gentle"
            }
        }
        return params_map.get(emotion, {
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "style": "general"
        })
        
    async def _detect_emotion(self, text: str) -> Emotion:
        """检测文本情感"""
        # 使用LLM或情感分析模型
        prompt = f"Detect emotion of text (HAPPY/SAD/ANGRY/NEUTRAL): {text}"
        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        emotion_text = response["content"].strip().upper()
        return Emotion[emotion_text]
```

**实现优先级**: P0  
**预计工作量**: 4周

---

## 3. RAG Engine

### 3.1 当前功能清单

#### ✅ 已实现

- 查询改写(multi-query, HyDE)
- 向量检索集成
- 上下文构建与截断
- 答案生成(流式/非流式)
- 引用生成

#### 🔄 待完善

- **Self-RAG**: 自适应检索决策
- **Rerank优化**: 多种重排序策略
- **缓存策略**: 查询结果缓存
- **评测体系**: RAG效果评测

### 3.2 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 3.2.1 Self-RAG实现

(参见Agent Engine章节的Self-RAG设计)

##### 3.2.2 智能查询改写

**功能描述**: 多策略查询改写,提升召回率

**设计方案**:

```python
# app/core/query_rewriter.py

class QueryRewriter:
    """查询改写器"""
    
    async def rewrite_query(
        self,
        query: str,
        method: str = "multi"
    ) -> List[str]:
        """改写查询"""
        if method == "multi":
            return await self._multi_query(query)
        elif method == "hyde":
            return await self._hyde(query)
        elif method == "decompose":
            return await self._decompose(query)
        elif method == "step_back":
            return await self._step_back(query)
        else:
            return [query]
            
    async def _multi_query(self, query: str, num_variants: int = 3) -> List[str]:
        """多查询生成"""
        prompt = f"""
        Generate {num_variants} different ways to ask the same question:
        
        Original: {query}
        
        Variants (one per line):
        """
        
        response = await self.llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        variants = response["content"].strip().split('\n')
        return [query] + [v.strip() for v in variants if v.strip()]
        
    async def _hyde(self, query: str) -> List[str]:
        """假设性文档生成"""
        prompt = f"""
        Generate a hypothetical document that would answer this question:
        
        Question: {query}
        
        Hypothetical Document:
        """
        
        response = await self.llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        hypothetical_doc = response["content"].strip()
        return [query, hypothetical_doc]
        
    async def _decompose(self, query: str) -> List[str]:
        """查询分解"""
        prompt = f"""
        Break down this complex question into simpler sub-questions:
        
        Question: {query}
        
        Sub-questions (one per line):
        """
        
        response = await self.llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        sub_questions = response["content"].strip().split('\n')
        return [query] + [q.strip() for q in sub_questions if q.strip()]
        
    async def _step_back(self, query: str) -> List[str]:
        """Step-back提示"""
        prompt = f"""
        Generate a more general question that helps answer the specific question:
        
        Specific: {query}
        
        General:
        """
        
        response = await self.llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        general_query = response["content"].strip()
        return [query, general_query]
```

**实现优先级**: P0  
**预计工作量**: 3周  

---

## 4. Retrieval Service

### 4.1 当前功能清单

#### ✅ 已实现

- 向量检索(Milvus)
- BM25检索(Elasticsearch)
- RRF混合融合
- Cross-Encoder重排序
- 多租户过滤

#### 🔄 待完善

- LLM重排序
- 缓存优化
- 索引自动优化
- 性能监控

### 4.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 4.2.1 LLM重排序

**功能描述**: 使用LLM对检索结果进行语义重排序

**设计方案**:

```python
# app/services/llm_rerank_service.py

class LLMRerankService:
    """LLM重排序服务"""
    
    async def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """LLM重排序"""
        # 1. 批量评分
        scores = await self._batch_score(query, chunks)
        
        # 2. 排序
        scored_chunks = list(zip(chunks, scores))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # 3. 返回top-k
        return [chunk for chunk, score in scored_chunks[:top_k]]
        
    async def _batch_score(
        self,
        query: str,
        chunks: List[Dict],
        batch_size: int = 10
    ) -> List[float]:
        """批量评分"""
        scores = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_scores = await self._score_batch(query, batch)
            scores.extend(batch_scores)
            
        return scores
        
    async def _score_batch(self, query: str, chunks: List[Dict]) -> List[float]:
        """对一批chunks评分"""
        # 构建提示
        chunks_text = "\n\n".join([
            f"[{i}] {chunk['content']}" 
            for i, chunk in enumerate(chunks)
        ])
        
        prompt = f"""
        Query: {query}
        
        Rate each passage's relevance to the query (0-10):
        
        {chunks_text}
        
        Scores (one per line):
        """
        
        response = await self.llm_client.chat([
            {"role": "user", "content": prompt}
        ])
        
        # 解析分数
        score_lines = response["content"].strip().split('\n')
        scores = []
        for line in score_lines:
            try:
                score = float(line.strip())
                scores.append(score / 10.0)  # 归一化到0-1
            except:
                scores.append(0.5)
                
        return scores
```

**实现优先级**: P1  
**预计工作量**: 2周

---

## 5. Model Adapter

### 5.1 当前功能清单

#### ✅ 已实现

- OpenAI适配器
- Azure OpenAI适配器
- Anthropic适配器(部分)

#### ❌ 待实现

- 智谱AI(GLM)适配器
- 通义千问(Qwen)适配器
- 百度文心(ERNIE)适配器
- 本地模型(Ollama/vLLM)

### 5.2 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 5.2.1 国产模型适配器

**实现清单**:

1. **智谱AI (GLM-4)**

```python
# app/services/providers/zhipu_adapter.py

class ZhipuAdapter(BaseAdapter):
    """智谱AI适配器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self.client = httpx.AsyncClient()
        
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天补全"""
        # 转换请求格式
        zhipu_request = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=zhipu_request,
            headers=headers,
            timeout=60
        )
        
        result = response.json()
        
        # 转换响应格式
        return ChatResponse(
            id=result["id"],
            model=result["model"],
            choices=[
                Choice(
                    message=Message(
                        role="assistant",
                        content=result["choices"][0]["message"]["content"]
                    ),
                    finish_reason=result["choices"][0]["finish_reason"]
                )
            ],
            usage=Usage(
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
                total_tokens=result["usage"]["total_tokens"]
            )
        )
        
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天"""
        zhipu_request = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=zhipu_request,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    yield self._format_chunk(chunk)
```

2. **通义千问 (Qwen)**

```python
# app/services/providers/qwen_adapter.py

class QwenAdapter(BaseAdapter):
    """通义千问适配器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"
        
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天补全"""
        import dashscope
        
        dashscope.api_key = self.api_key
        
        response = dashscope.Generation.call(
            model=request.model,
            messages=request.messages,
            result_format='message'
        )
        
        if response.status_code == 200:
            return self._convert_response(response)
        else:
            raise Exception(f"Qwen API error: {response.message}")
```

3. **百度文心 (ERNIE)**

```python
# app/services/providers/baidu_adapter.py

class BaiduAdapter(BaseAdapter):
    """百度文心适配器"""
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        
    async def _get_access_token(self) -> str:
        """获取access token"""
        if self.access_token:
            return self.access_token
            
        url = f"https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        response = await self.client.post(url, params=params)
        result = response.json()
        self.access_token = result["access_token"]
        return self.access_token
        
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天补全"""
        access_token = await self._get_access_token()
        
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"
        params = {"access_token": access_token}
        
        baidu_request = {
            "messages": request.messages,
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens
        }
        
        response = await self.client.post(url, json=baidu_request, params=params)
        result = response.json()
        
        return self._convert_response(result)
```

**实现优先级**: P0  
**预计工作量**: 4周  
**负责人**: 算法工程师

---

## 6. Indexing Service

### 6.1 当前功能清单

#### ✅ 已实现

- PDF/Word/Markdown解析
- 文本分块
- Embedding生成
- Kafka消费者
- 元数据提取

#### 🔄 待完善

- OCR支持
- 表格提取
- 图表理解
- 语义分块

### 6.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 6.2.1 语义分块

**功能描述**: 基于语义相似度的智能分块

**设计方案**:

```python
# app/core/semantic_chunker.py

from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticChunker:
    """语义分块器"""
    
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 100,
        max_chunk_size: int = 500
    ):
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
    def chunk(self, text: str) -> List[str]:
        """语义分块"""
        # 1. 按句子分割
        sentences = self._split_sentences(text)
        
        # 2. 计算句子embedding
        embeddings = self.model.encode(sentences)
        
        # 3. 计算相似度
        similarities = self._compute_similarities(embeddings)
        
        # 4. 基于相似度分组
        chunks = []
        current_chunk = []
        current_length = 0
        
        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence)
            current_length += len(sentence)
            
            # 检查是否应该分块
            should_split = False
            
            # 条件1: 长度超过最大值
            if current_length >= self.max_chunk_size:
                should_split = True
                
            # 条件2: 相似度低于阈值
            if i < len(similarities) and similarities[i] < self.similarity_threshold:
                if current_length >= self.min_chunk_size:
                    should_split = True
                    
            if should_split:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0
                
        # 添加最后一个chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        return chunks
        
    def _compute_similarities(self, embeddings: np.ndarray) -> List[float]:
        """计算相邻句子相似度"""
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i+1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1])
            )
            similarities.append(sim)
        return similarities
```

**实现优先级**: P1  
**预计工作量**: 3周

---

## 7. Multimodal Engine

### 7.1 当前功能清单

#### 🔄 部分完成

- 图像理解基础框架
- OCR集成
- 视频处理骨架

#### ❌ 待实现

- 图文混合检索
- 视频摘要生成
- 图表解析
- 多模态Embedding

### 7.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 7.2.1 图像理解

**功能描述**: 图像OCR、物体识别、场景理解

**设计方案**:

```python
# app/services/image_understanding_service.py

from transformers import pipeline
import pytesseract
from PIL import Image

class ImageUnderstandingService:
    """图像理解服务"""
    
    def __init__(self):
        # OCR
        self.ocr_engine = pytesseract
        
        # 物体检测
        self.object_detector = pipeline("object-detection", model="facebook/detr-resnet-50")
        
        # 图像描述
        self.image_captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
        
    async def understand_image(self, image_path: str) -> Dict[str, Any]:
        """理解图像"""
        image = Image.open(image_path)
        
        # 1. OCR提取文字
        text = self.ocr_engine.image_to_string(image, lang='chi_sim+eng')
        
        # 2. 物体检测
        objects = self.object_detector(image)
        
        # 3. 生成图像描述
        caption = self.image_captioner(image)[0]['generated_text']
        
        return {
            "text": text,
            "objects": objects,
            "caption": caption,
            "image_path": image_path
        }
```

**实现优先级**: P1  
**预计工作量**: 6周

---

## 8. Knowledge Service (Python)

### 8.1 当前功能清单

#### 🔄 部分完成

- 知识图谱基础框架
- 图谱查询接口

#### ❌ 待实现

- 实体关系抽取
- 图谱构建流程
- 图谱推理
- 知识融合

### 8.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 8.2.1 实体关系抽取

**功能描述**: 从文本中自动抽取实体和关系

**设计方案**:

```python
# app/services/entity_extraction_service.py

class EntityExtractionService:
    """实体关系抽取服务"""
    
    async def extract(self, text: str) -> Dict[str, Any]:
        """抽取实体和关系"""
        # 1. 命名实体识别
        entities = await self._extract_entities(text)
        
        # 2. 关系抽取
        relations = await self._extract_relations(text, entities)
        
        # 3. 三元组构建
        triples = self._build_triples(entities, relations)
        
        return {
            "entities": entities,
            "relations": relations,
            "triples": triples
        }
        
    async def _extract_entities(self, text: str) -> List[Dict]:
        """NER"""
        prompt = f"""
        Extract named entities from the text:
        
        Text: {text}
        
        Return JSON:
        [
          {{"text": "entity1", "type": "PERSON"}},
          {{"text": "entity2", "type": "ORG"}}
        ]
        """
        
        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        entities = json.loads(response["content"])
        return entities
        
    async def _extract_relations(self, text: str, entities: List[Dict]) -> List[Dict]:
        """关系抽取"""
        entity_texts = [e["text"] for e in entities]
        
        prompt = f"""
        Extract relations between entities:
        
        Text: {text}
        Entities: {entity_texts}
        
        Return JSON:
        [
          {{"subject": "entity1", "predicate": "works_for", "object": "entity2"}}
        ]
        """
        
        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        relations = json.loads(response["content"])
        return relations
        
    def _build_triples(self, entities: List[Dict], relations: List[Dict]) -> List[Tuple]:
        """构建三元组"""
        triples = []
        for rel in relations:
            triples.append((rel["subject"], rel["predicate"], rel["object"]))
        return triples
```

**实现优先级**: P1  
**预计工作量**: 8周

---

## 9. Vector Store Adapter

### 9.1 当前功能清单

#### ✅ 已实现

- Milvus适配器
- Qdrant适配器(部分)
- Weaviate适配器(骨架)

#### 🔄 待完善

- Pinecone适配器
- 连接池管理
- 自动重连
- 性能监控

### 9.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 9.2.1 连接池优化

**功能描述**: 提升向量数据库连接效率

**设计方案**:

```python
# app/core/connection_pool.py

from typing import Optional
import asyncio

class ConnectionPool:
    """连接池"""
    
    def __init__(
        self,
        backend: str,
        host: str,
        port: int,
        min_size: int = 5,
        max_size: int = 20
    ):
        self.backend = backend
        self.host = host
        self.port = port
        self.min_size = min_size
        self.max_size = max_size
        
        self.pool = asyncio.Queue(maxsize=max_size)
        self.size = 0
        
    async def initialize(self):
        """初始化连接池"""
        for _ in range(self.min_size):
            conn = await self._create_connection()
            await self.pool.put(conn)
            
    async def get_connection(self):
        """获取连接"""
        if self.pool.empty() and self.size < self.max_size:
            conn = await self._create_connection()
            return conn
        return await self.pool.get()
        
    async def return_connection(self, conn):
        """归还连接"""
        if not self.pool.full():
            await self.pool.put(conn)
        else:
            await self._close_connection(conn)
            
    async def _create_connection(self):
        """创建连接"""
        if self.backend == "milvus":
            from pymilvus import connections
            conn = connections.connect(host=self.host, port=self.port)
            self.size += 1
            return conn
```

**实现优先级**: P1  
**预计工作量**: 2周

---

## 📈 总体进度追踪

### 时间线

```
Q2 2025 (Apr-Jun)
├── Week 1-8:  Multi-Agent + Self-RAG
├── Week 9-16: 实时语音对话 + 情感TTS
└── Week 17-24: 国产模型适配 + 工具市场

Q3 2025 (Jul-Sep)
├── Week 1-8:  语义分块 + LLM重排
├── Week 9-16: 图像理解 + 视频处理
└── Week 17-24: 知识图谱 + 实体抽取

Q4 2025 (Oct-Dec)
├── Week 1-8:  DAG工作流 + 性能优化
├── Week 9-16: 插件生态 + SDK
└── Week 17-24: 文档完善 + 压测调优
```

### 资源需求

| 角色 | 人数 | Q2工作量 | Q3工作量 | Q4工作量 |
|------|------|---------|---------|---------|
| 算法工程师(Python) | 2 | 100% | 100% | 80% |
| ML工程师 | 1 | 80% | 100% | 60% |
| 测试工程师 | 1 | 50% | 60% | 80% |

### 里程碑

- **M1 (2025-06-30)**: P0核心功能完成(Multi-Agent, Self-RAG, 实时语音)
- **M2 (2025-09-30)**: P1功能完成(知识图谱, 多模态, LLM重排)
- **M3 (2025-12-31)**: 系统优化与生态建设完成

---

## 📞 联系方式

**负责人**: 算法团队  
**邮箱**: algo-team@voiceassistant.com  
**文档更新**: 每月1号更新进度

---

**最后更新**: 2025-10-27  
**下次Review**: 2025-11-27
