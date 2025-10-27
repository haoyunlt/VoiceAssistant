# Agent Engine 服务功能清单与迭代计划

## 服务概述

Agent Engine 是 AI Agent 执行引擎，负责基于 ReAct 模式的智能任务执行、工具调用、推理链和异步任务管理。

**技术栈**: FastAPI + Python 3.11+ + OpenAI API + LangGraph

**端口**: 8003

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 核心 Agent 功能
- ✅ ReAct 模式执行器
- ✅ 同步任务执行
- ✅ 异步任务执行
- ✅ 任务状态跟踪
- ✅ 迭代控制与超时管理

#### 2. 工具系统
- ✅ 计算器工具
- ✅ 搜索工具（示例实现）
- ✅ 知识库查询工具（示例实现）
- ✅ 工具注册机制
- ✅ 工具参数验证

#### 3. API 接口
- ✅ `/api/v1/agent/execute` - 同步执行
- ✅ `/api/v1/agent/execute-async` - 异步执行
- ✅ `/api/v1/agent/task/{task_id}` - 任务查询
- ✅ `/api/v1/tools/list` - 工具列表
- ✅ `/api/v1/tools/{tool_name}/execute` - 工具执行
- ✅ `/health` - 健康检查

#### 4. 基础设施
- ✅ FastAPI 应用框架
- ✅ Pydantic 数据模型
- ✅ 日志配置
- ✅ 配置管理
- ✅ Docker 支持

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代1：2周）

#### 1. 高级 Executor 实现
**当前状态**: 部分实现，需要完善

**位置**: `algo/agent-engine/app/executors/`

**待实现**:

##### 1.1 Plan-Execute Executor
```python
# 文件: algo/agent-engine/app/executors/plan_execute_executor.py
# 当前TODO: 第335行 - 调用 LLM，第97行 - 实际应该解析步骤

class PlanExecuteExecutor:
    async def execute(self, task: str) -> dict:
        """
        计划-执行模式执行器
        1. 分解任务为子任务
        2. 为每个子任务生成执行计划
        3. 按顺序执行子任务
        4. 汇总结果
        """
        # Step 1: 使用 LLM 分解任务
        plan = await self._generate_plan(task)
        
        # Step 2: 执行每个子任务
        results = []
        for step in plan.steps:
            result = await self._execute_step(step)
            results.append(result)
            
        # Step 3: 汇总结果
        final_answer = await self._summarize_results(results)
        return {
            "answer": final_answer,
            "plan": plan,
            "step_results": results
        }
    
    async def _generate_plan(self, task: str) -> Plan:
        """使用 LLM 生成执行计划"""
        prompt = f"""
        分解以下任务为多个子任务:
        任务: {task}
        
        请以 JSON 格式返回计划:
        {{
            "steps": [
                {{"id": 1, "description": "子任务1", "dependencies": []}},
                {{"id": 2, "description": "子任务2", "dependencies": [1]}}
            ]
        }}
        """
        
        response = await self.llm_client.complete(prompt)
        return Plan.parse_raw(response)
    
    async def _execute_step(self, step: Step) -> StepResult:
        """执行单个步骤"""
        # 选择合适的工具
        tool = self._select_tool(step.description)
        
        # 提取参数
        params = self._extract_params(step.description, tool)
        
        # 执行工具
        result = await tool.execute(params)
        
        return StepResult(
            step_id=step.id,
            output=result,
            status="completed"
        )
```

**验收标准**:
- [ ] 能够自动分解复杂任务
- [ ] 支持子任务依赖关系
- [ ] 支持并行执行独立子任务
- [ ] 完整的错误处理和回滚

##### 1.2 Reflexion Executor
```python
# 文件: algo/agent-engine/app/executors/reflexion_executor.py
# 新文件，需要创建

class ReflexionExecutor:
    """
    Reflexion 执行器 - 支持自我反思和改进
    """
    
    async def execute(self, task: str, max_trials: int = 3) -> dict:
        """
        带反思的执行
        1. 尝试执行任务
        2. 评估结果
        3. 如果不满意，反思并重试
        """
        history = []
        
        for trial in range(max_trials):
            # 执行任务
            result = await self._attempt_task(task, history)
            
            # 评估结果
            evaluation = await self._evaluate_result(task, result)
            
            if evaluation.is_satisfactory:
                return result
            
            # 反思
            reflection = await self._reflect(task, result, evaluation)
            history.append({
                "trial": trial + 1,
                "result": result,
                "reflection": reflection
            })
        
        # 所有尝试都失败，返回最好的结果
        return self._select_best_result(history)
    
    async def _evaluate_result(self, task: str, result: dict) -> Evaluation:
        """评估结果质量"""
        prompt = f"""
        任务: {task}
        结果: {result['answer']}
        
        请评估这个结果是否正确、完整、合理。
        返回 JSON:
        {{
            "is_satisfactory": true/false,
            "score": 0.0-1.0,
            "issues": ["问题1", "问题2"]
        }}
        """
        
        response = await self.llm_client.complete(prompt)
        return Evaluation.parse_raw(response)
    
    async def _reflect(self, task: str, result: dict, evaluation: Evaluation) -> str:
        """生成反思"""
        prompt = f"""
        任务: {task}
        上次尝试: {result['answer']}
        存在问题: {evaluation.issues}
        
        请分析失败原因，并提出改进建议。
        """
        
        return await self.llm_client.complete(prompt)
```

**验收标准**:
- [ ] 支持多轮反思和重试
- [ ] 能够从失败中学习
- [ ] 提供详细的反思记录
- [ ] 最终结果质量明显提升

#### 2. 工具系统增强

##### 2.1 真实工具集成
```python
# 文件: algo/agent-engine/app/services/tool_service.py
# 当前TODO: 第218行 - 接入真实搜索API

class ToolService:
    def _search_tool(self, query: str) -> str:
        """
        集成真实搜索 API
        - Google Custom Search
        - Bing Search API
        - DuckDuckGo API
        """
        try:
            # 优先使用 SerpAPI
            if os.getenv("SERPAPI_KEY"):
                return self._search_with_serpapi(query)
            
            # 备选 DuckDuckGo
            return self._search_with_duckduckgo(query)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"搜索失败: {str(e)}"
    
    def _search_with_serpapi(self, query: str) -> str:
        """使用 SerpAPI 搜索"""
        import serpapi
        
        client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))
        results = client.search({
            "engine": "google",
            "q": query,
            "num": 5
        })
        
        # 提取搜索结果
        snippets = []
        for result in results.get("organic_results", [])[:5]:
            snippets.append(f"{result['title']}: {result['snippet']}")
        
        return "\n\n".join(snippets)
    
    def _search_with_duckduckgo(self, query: str) -> str:
        """使用 DuckDuckGo 搜索"""
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            
        snippets = [f"{r['title']}: {r['body']}" for r in results]
        return "\n\n".join(snippets)
```

##### 2.2 新增工具
```python
# 天气查询工具
def register_weather_tool(self):
    """
    集成 OpenWeatherMap API
    """
    self.register_tool(
        name="weather",
        description="查询指定城市的天气信息",
        function=self._weather_tool,
        parameters={
            "city": {
                "type": "string",
                "description": "城市名称"
            }
        },
        required_params=["city"]
    )

def _weather_tool(self, city: str) -> str:
    """查询天气"""
    import requests
    
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/weather"
    
    response = requests.get(url, params={
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "zh_cn"
    })
    
    data = response.json()
    return f"{city}天气: {data['weather'][0]['description']}, 温度: {data['main']['temp']}°C"

# 文件操作工具
def register_file_tool(self):
    """安全的文件读取工具"""
    self.register_tool(
        name="read_file",
        description="读取指定文件的内容",
        function=self._read_file_tool,
        parameters={
            "file_path": {
                "type": "string",
                "description": "文件路径"
            }
        },
        required_params=["file_path"]
    )

def _read_file_tool(self, file_path: str) -> str:
    """读取文件（带安全检查）"""
    # 安全检查
    allowed_dirs = ["/app/data", "/tmp"]
    if not any(file_path.startswith(d) for d in allowed_dirs):
        return "错误: 无权访问该目录"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(10000)  # 限制大小
        return content
    except Exception as e:
        return f"读取失败: {str(e)}"
```

**验收标准**:
- [ ] 搜索工具返回真实结果
- [ ] 知识库工具连接真实服务
- [ ] 新增至少5个实用工具
- [ ] 所有工具有完整的错误处理

#### 3. 动态工具注册
```python
# 文件: algo/agent-engine/main.py
# 当前TODO: 第288行 - 实现动态工具注册

class DynamicToolRegistry:
    """动态工具注册中心"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_store_path = "/app/tools"
    
    async def register_from_yaml(self, yaml_path: str):
        """从 YAML 文件加载工具定义"""
        with open(yaml_path) as f:
            tool_def = yaml.safe_load(f)
        
        tool = Tool(
            name=tool_def["name"],
            description=tool_def["description"],
            function=self._create_http_tool(tool_def["endpoint"]),
            parameters=tool_def["parameters"]
        )
        
        self.tools[tool.name] = tool
    
    def _create_http_tool(self, endpoint: str) -> Callable:
        """创建 HTTP 工具函数"""
        async def http_tool(**kwargs):
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=kwargs)
                return response.json()
        return http_tool
    
    async def register_from_api(self, api_url: str):
        """从远程 API 注册工具"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/tools")
            tools = response.json()
            
        for tool_def in tools:
            await self.register_from_dict(tool_def)

# API 端点
@app.post("/api/v1/tools/register")
async def register_tool(tool_def: ToolDefinition):
    """动态注册新工具"""
    registry.register_from_dict(tool_def.dict())
    return {"status": "registered", "tool": tool_def.name}
```

**验收标准**:
- [ ] 支持从 YAML 加载工具
- [ ] 支持从远程 API 注册工具
- [ ] 支持 HTTP 工具包装
- [ ] 提供工具注册 API

#### 4. Memory 系统完善
```python
# 文件: algo/agent-engine/app/memory/memory_manager.py
# 当前TODO: 第209行 - 实现向量检索，第282、306行 - 实现向量存储

class VectorMemoryManager:
    """基于向量的记忆管理"""
    
    def __init__(self):
        self.milvus_client = MilvusClient(
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530")
        )
        self.collection_name = "agent_memory"
        self._init_collection()
    
    def _init_collection(self):
        """初始化 Milvus collection"""
        schema = {
            "fields": [
                {"name": "memory_id", "type": "VARCHAR", "max_length": 64, "is_primary": True},
                {"name": "conversation_id", "type": "VARCHAR", "max_length": 64},
                {"name": "content", "type": "VARCHAR", "max_length": 2000},
                {"name": "embedding", "type": "FLOAT_VECTOR", "dim": 1536},
                {"name": "timestamp", "type": "INT64"}
            ]
        }
        
        if not self.milvus_client.has_collection(self.collection_name):
            self.milvus_client.create_collection(
                collection_name=self.collection_name,
                schema=schema
            )
    
    async def store_memory(self, memory: Memory):
        """存储记忆（向量化）"""
        # 1. 生成向量
        embedding = await self._get_embedding(memory.content)
        
        # 2. 插入 Milvus
        self.milvus_client.insert(
            collection_name=self.collection_name,
            data=[{
                "memory_id": memory.id,
                "conversation_id": memory.conversation_id,
                "content": memory.content,
                "embedding": embedding,
                "timestamp": int(time.time())
            }]
        )
    
    async def search_memory(self, query: str, top_k: int = 5) -> List[Memory]:
        """向量检索相关记忆"""
        # 1. 查询向量化
        query_embedding = await self._get_embedding(query)
        
        # 2. 向量搜索
        results = self.milvus_client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            limit=top_k,
            output_fields=["memory_id", "content", "timestamp"]
        )
        
        # 3. 转换为 Memory 对象
        memories = []
        for hit in results[0]:
            memories.append(Memory(
                id=hit["memory_id"],
                content=hit["content"],
                timestamp=hit["timestamp"]
            ))
        
        return memories
    
    async def _get_embedding(self, text: str) -> List[float]:
        """获取文本向量"""
        # 调用 Model Adapter 的 embedding 接口
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MODEL_ADAPTER_URL}/api/v1/embedding/create",
                json={"input": text, "model": "text-embedding-3-small"}
            )
            data = response.json()
            return data["data"][0]["embedding"]
```

**验收标准**:
- [ ] 记忆向量化存储到 Milvus
- [ ] 基于语义相似度检索记忆
- [ ] 支持对话级记忆隔离
- [ ] 提供记忆统计和清理功能

#### 5. Task Manager 增强
```python
# 文件: algo/agent-engine/app/services/task_manager.py
# 已创建但需要完善

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )
    
    async def create_task(self, task_input: TaskInput) -> Task:
        """创建任务"""
        task = Task(
            id=f"task_{uuid.uuid4().hex}",
            type=task_input.type,
            input=task_input.input,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # 存储到 Redis
        await self._save_task(task)
        
        # 异步执行
        asyncio.create_task(self._execute_task(task))
        
        return task
    
    async def cancel_task(self, task_id: str):
        """取消任务"""
        task = await self.get_task(task_id)
        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            await self._save_task(task)
    
    async def get_task(self, task_id: str) -> Task:
        """获取任务"""
        data = self.redis_client.get(f"task:{task_id}")
        if not data:
            raise TaskNotFound(task_id)
        return Task.parse_raw(data)
    
    async def _execute_task(self, task: Task):
        """执行任务"""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            await self._save_task(task)
            
            # 根据类型选择执行器
            executor = self._get_executor(task.type)
            result = await executor.execute(task.input)
            
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.utcnow()
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            
        finally:
            await self._save_task(task)
```

**验收标准**:
- [ ] 任务持久化到 Redis
- [ ] 支持任务取消
- [ ] 任务状态实时查询
- [ ] 完整的生命周期管理

---

### 🔄 P1 - 高级功能（迭代2：2周）

#### 1. WebSocket 流式执行
```python
# 文件: algo/agent-engine/app/websocket/message_handler.py
# 当前TODO: 第232行 - 实现任务取消逻辑

@app.websocket("/ws/agent/stream")
async def agent_stream(websocket: WebSocket):
    """WebSocket 流式执行"""
    await websocket.accept()
    
    try:
        while True:
            # 接收请求
            message = await websocket.receive_json()
            
            if message["type"] == "execute":
                # 流式执行
                async for chunk in agent_service.execute_stream(message["task"]):
                    await websocket.send_json({
                        "type": "chunk",
                        "data": chunk
                    })
                
                await websocket.send_json({"type": "done"})
                
            elif message["type"] == "cancel":
                # 取消任务
                await task_manager.cancel_task(message["task_id"])
                await websocket.send_json({"type": "cancelled"})
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

**验收标准**:
- [ ] 支持 WebSocket 连接
- [ ] 实时流式输出
- [ ] 支持任务取消
- [ ] 连接状态管理

#### 2. Multi-Agent 协作
```python
# 新文件: algo/agent-engine/app/multi_agent/coordinator.py

class MultiAgentCoordinator:
    """多 Agent 协调器"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
    
    async def register_agent(self, agent: Agent):
        """注册 Agent"""
        self.agents[agent.name] = agent
    
    async def execute_collaborative_task(self, task: str) -> dict:
        """
        协作执行任务
        1. 任务分解
        2. 分配给合适的 Agent
        3. 协调执行
        4. 结果合并
        """
        # 1. 分解任务
        subtasks = await self._decompose_task(task)
        
        # 2. 分配任务
        assignments = await self._assign_tasks(subtasks)
        
        # 3. 并行执行
        results = await asyncio.gather(*[
            self._execute_subtask(agent, subtask)
            for agent, subtask in assignments
        ])
        
        # 4. 合并结果
        final_result = await self._merge_results(results)
        
        return final_result
    
    async def _assign_tasks(self, subtasks: List[str]) -> List[Tuple[Agent, str]]:
        """根据 Agent 能力分配任务"""
        assignments = []
        for subtask in subtasks:
            # 选择最合适的 Agent
            agent = await self._select_agent(subtask)
            assignments.append((agent, subtask))
        return assignments
```

**验收标准**:
- [ ] 支持多个 Agent 注册
- [ ] 智能任务分配
- [ ] 并行执行和结果合并
- [ ] Agent 间通信机制

#### 3. LangGraph 集成
```python
# 新文件: algo/agent-engine/app/graph/langgraph_executor.py

from langgraph.graph import StateGraph, END

class LangGraphExecutor:
    """LangGraph 工作流执行器"""
    
    def build_rag_agent_graph(self):
        """构建 RAG Agent 图"""
        # 定义状态
        class AgentState(TypedDict):
            query: str
            documents: List[str]
            answer: str
        
        # 创建图
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("retrieve", self._retrieve_documents)
        workflow.add_node("rerank", self._rerank_documents)
        workflow.add_node("generate", self._generate_answer)
        
        # 添加边
        workflow.add_edge("retrieve", "rerank")
        workflow.add_edge("rerank", "generate")
        workflow.add_edge("generate", END)
        
        # 设置入口
        workflow.set_entry_point("retrieve")
        
        return workflow.compile()
    
    async def _retrieve_documents(self, state: AgentState) -> AgentState:
        """检索文档"""
        # 调用检索服务
        documents = await retrieval_service.search(state["query"])
        state["documents"] = documents
        return state
    
    async def _rerank_documents(self, state: AgentState) -> AgentState:
        """重排序"""
        # 调用重排序
        reranked = await rerank_service.rerank(
            state["query"], 
            state["documents"]
        )
        state["documents"] = reranked
        return state
    
    async def _generate_answer(self, state: AgentState) -> AgentState:
        """生成答案"""
        # 调用 LLM
        answer = await llm_service.generate(
            query=state["query"],
            context=state["documents"]
        )
        state["answer"] = answer
        return state
```

**验收标准**:
- [ ] 集成 LangGraph
- [ ] 支持自定义工作流图
- [ ] 状态管理和流转
- [ ] 条件分支和循环

---

### 🔄 P2 - 优化增强（迭代3：1周）

#### 1. 性能优化
- [ ] LLM 调用缓存（Redis）
- [ ] 工具结果缓存
- [ ] 并发限流
- [ ] 连接池优化

#### 2. 可观测性
- [ ] Prometheus 指标
- [ ] OpenTelemetry Trace
- [ ] 详细日志
- [ ] 性能分析

#### 3. 安全增强
- [ ] 工具权限控制
- [ ] 敏感信息过滤
- [ ] 沙箱执行环境
- [ ] API 密钥管理

---

## 三、详细实施方案

### 阶段1：核心功能完善（Week 1-2）

**目标**: 完成 P0 功能

#### Day 1-3: Executor 实现
1. 实现 Plan-Execute Executor
2. 实现 Reflexion Executor
3. 编写单元测试

#### Day 4-6: 工具系统增强
1. 集成真实搜索 API
2. 实现天气、文件等新工具
3. 实现动态工具注册

#### Day 7-10: Memory 和 Task Manager
1. 完成向量记忆系统
2. 完善任务管理器
3. 集成测试

#### Day 11-14: 集成和测试
1. 端到端测试
2. 性能测试
3. 文档更新

### 阶段2：高级功能（Week 3-4）

**目标**: 完成 P1 功能

#### Day 15-18: WebSocket 和 Multi-Agent
1. 实现 WebSocket 流式执行
2. 实现多 Agent 协调
3. 测试

#### Day 19-22: LangGraph 集成
1. 集成 LangGraph
2. 构建示例工作流
3. 文档和示例

#### Day 23-28: 优化和完善
1. 性能优化
2. 可观测性
3. 安全增强

---

## 四、验收标准

### 功能验收
- [ ] 所有 P0 功能完成并测试通过
- [ ] 所有 P1 功能完成并测试通过
- [ ] 单元测试覆盖率 >= 70%
- [ ] 集成测试通过

### 性能验收
- [ ] 简单任务响应时间 < 2s
- [ ] 复杂任务响应时间 < 10s
- [ ] 支持 100 并发请求
- [ ] LLM 缓存命中率 > 30%

### 质量验收
- [ ] 代码通过 Lint 检查
- [ ] 所有 TODO 清理完毕
- [ ] API 文档完整
- [ ] 运维文档完整

---

## 五、依赖和风险

### 外部依赖
- Model Adapter 服务（LLM 调用）
- Retrieval Service（知识库查询）
- Milvus（向量存储）
- Redis（缓存和任务队列）

### 风险项
1. **LLM API 稳定性**: 依赖第三方 API，可能不稳定
   - 缓解: 实现重试和降级机制
   
2. **工具安全性**: 动态工具可能带来安全风险
   - 缓解: 实现沙箱和权限控制
   
3. **性能瓶颈**: 复杂任务可能很慢
   - 缓解: 异步执行、缓存优化

---

## 六、关键代码示例

### 完整的 ReAct 执行流程
```python
class EnhancedReActExecutor:
    """增强的 ReAct 执行器"""
    
    async def execute(
        self,
        task: str,
        max_iterations: int = 10,
        timeout: int = 300
    ) -> AgentResult:
        """
        执行 ReAct 循环
        """
        start_time = time.time()
        history = []
        
        for iteration in range(max_iterations):
            # 检查超时
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Task timeout after {timeout}s")
            
            # Step 1: Thought (思考)
            thought = await self._generate_thought(task, history)
            
            # Step 2: Action (决策)
            action = await self._parse_action(thought)
            
            if action.type == "finish":
                # 完成
                return AgentResult(
                    answer=action.answer,
                    iterations=iteration + 1,
                    history=history,
                    duration=time.time() - start_time
                )
            
            # Step 3: Execute (执行)
            observation = await self._execute_tool(
                action.tool_name,
                action.tool_input
            )
            
            # Step 4: Record (记录)
            history.append({
                "iteration": iteration + 1,
                "thought": thought,
                "action": action.dict(),
                "observation": observation
            })
        
        # 达到最大迭代次数
        raise MaxIterationsError(
            f"Max iterations ({max_iterations}) reached"
        )
    
    async def _generate_thought(
        self,
        task: str,
        history: List[dict]
    ) -> str:
        """生成思考"""
        prompt = self._build_react_prompt(task, history)
        
        # 调用 LLM
        response = await self.llm_client.complete(
            prompt=prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        return response
    
    def _build_react_prompt(
        self,
        task: str,
        history: List[dict]
    ) -> str:
        """构建 ReAct Prompt"""
        prompt = f"""
你是一个智能助手，能够使用工具完成任务。

任务: {task}

可用工具:
{self._format_tools()}

请按照以下格式思考和行动:

Thought: 我需要做什么
Action: 工具名称
Action Input: 工具参数
Observation: 工具执行结果
... (重复以上步骤直到找到答案)
Thought: 我现在知道最终答案了
Action: finish
Action Input: 最终答案

开始!

"""
        
        # 添加历史
        for item in history:
            prompt += f"Thought: {item['thought']}\n"
            prompt += f"Action: {item['action']['tool_name']}\n"
            prompt += f"Action Input: {item['action']['tool_input']}\n"
            prompt += f"Observation: {item['observation']}\n\n"
        
        prompt += "Thought: "
        
        return prompt
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict
    ) -> str:
        """执行工具"""
        tool = self.tool_registry.get_tool(tool_name)
        
        if not tool:
            return f"错误: 工具 '{tool_name}' 不存在"
        
        try:
            result = await tool.execute(**tool_input)
            return str(result)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"工具执行失败: {str(e)}"
```

---

## 七、测试计划

### 单元测试
```python
# tests/test_executors.py

@pytest.mark.asyncio
async def test_plan_execute_executor():
    """测试 Plan-Execute 执行器"""
    executor = PlanExecuteExecutor()
    
    task = "查找最新的 AI 新闻并总结前3条"
    result = await executor.execute(task)
    
    assert result["answer"]
    assert len(result["plan"]["steps"]) > 0
    assert len(result["step_results"]) > 0

@pytest.mark.asyncio
async def test_reflexion_executor():
    """测试 Reflexion 执行器"""
    executor = ReflexionExecutor()
    
    task = "计算 123 * 456 并验证结果"
    result = await executor.execute(task, max_trials=3)
    
    assert "56088" in result["answer"]
    assert result["trials"] <= 3

@pytest.mark.asyncio
async def test_tool_execution():
    """测试工具执行"""
    tool_service = ToolService()
    
    # 测试计算器
    result = await tool_service.execute_tool(
        "calculator",
        {"expression": "10 + 20 * 3"}
    )
    assert result == "70"
    
    # 测试搜索
    result = await tool_service.execute_tool(
        "search",
        {"query": "Python tutorial"}
    )
    assert len(result) > 0
```

### 集成测试
```python
# tests/integration/test_agent_e2e.py

@pytest.mark.asyncio
async def test_agent_end_to_end():
    """端到端测试"""
    agent_service = AgentService()
    
    # 复杂任务
    task = """
    1. 查找今天北京的天气
    2. 如果温度低于10度，建议穿什么衣服
    3. 查找北京附近的景点推荐
    """
    
    result = await agent_service.execute(
        task=task,
        tools=["weather", "search"],
        max_iterations=15
    )
    
    assert result["answer"]
    assert result["success"]
    assert len(result["steps"]) > 0
```

---

## 八、文档更新

### API 文档
- [ ] 更新 Swagger/OpenAPI 文档
- [ ] 添加所有新接口文档
- [ ] 添加示例和最佳实践

### 开发文档
- [ ] Executor 开发指南
- [ ] 工具开发指南
- [ ] LangGraph 使用指南
- [ ] 性能优化指南

### 运维文档
- [ ] 部署指南
- [ ] 配置说明
- [ ] 监控告警
- [ ] 故障排查

---

## 总结

本迭代计划覆盖 Agent Engine 的所有待完成功能，预计 4 周完成。重点关注：

1. **高级 Executor**: Plan-Execute 和 Reflexion
2. **工具系统**: 真实 API 集成和动态注册
3. **Memory 系统**: 向量记忆和语义检索
4. **Multi-Agent**: 协作和 LangGraph

完成后，Agent Engine 将具备生产级能力，支持复杂的 AI Agent 任务。


