# Agent Engine - 功能清单与迭代计划

> **服务名称**: Agent Engine (algo/agent-engine)
> **当前版本**: v1.0.0
> **完成度**: 60%
> **优先级**: P0 (核心服务)

---

## 📊 执行摘要

Agent Engine 是 VoiceAssistant 平台的智能代理执行引擎，负责复杂任务的分解、工具调用和多步推理。当前已实现基础 ReAct 框架，但仍有多项关键功能待完善。

### 关键指标

| 指标       | 当前状态  | 目标状态             | 差距  |
| ---------- | --------- | -------------------- | ----- |
| 记忆系统   | Mock 实现 | 向量化持久记忆       | ⚠️ 高 |
| 工具数量   | 3 个 Mock | 10+实际工具          | ⚠️ 高 |
| 推理策略   | 仅 ReAct  | ReAct + Plan&Execute | ⚠️ 中 |
| 流式输出   | 不支持    | 完整支持             | ⚠️ 中 |
| 任务持久化 | 内存      | Redis 持久化         | ⚠️ 高 |

---

## 🔍 未完成功能清单 (基于 TODO 扫描)

### P0 级别 (阻塞性功能)

#### 1. 记忆管理 - 向量检索

**文件**: `app/memory/memory_manager.py:209,282,306`

**问题描述**:

```python
# Line 209
# TODO: 实现基于向量相似度的检索

# Line 282
# TODO: 实现向量存储

# Line 306
# TODO: 实现向量检索
```

**影响**: Agent 无法进行个性化对话和知识积累

**详细设计方案**:

```python
# app/memory/vector_memory.py

from typing import List, Dict, Optional
import numpy as np
from datetime import datetime
import httpx

class VectorMemoryManager:
    """基于向量数据库的长期记忆管理"""

    def __init__(
        self,
        milvus_url: str = "http://milvus:19530",
        embedding_service_url: str = "http://model-adapter:8002"
    ):
        self.milvus_url = milvus_url
        self.embedding_service_url = embedding_service_url
        self.collection_name = "agent_memory"
        self._init_collection()

    def _init_collection(self):
        """初始化Milvus集合"""
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

        fields = [
            FieldSchema(name="memory_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="memory_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="importance", dtype=DataType.FLOAT),
            FieldSchema(name="access_count", dtype=DataType.INT32),
            FieldSchema(name="last_accessed", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description="Agent Long-term Memory")
        collection = Collection(name=self.collection_name, schema=schema)

        # 创建索引
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()

    async def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "conversation",
        importance: float = 0.5
    ) -> str:
        """存储新记忆"""
        import uuid
        from pymilvus import Collection

        # 生成embedding
        embedding = await self._get_embedding(content)

        memory_id = str(uuid.uuid4())
        memory_data = [{
            "memory_id": memory_id,
            "user_id": user_id,
            "content": content,
            "memory_type": memory_type,
            "embedding": embedding,
            "created_at": int(datetime.now().timestamp()),
            "importance": importance,
            "access_count": 0,
            "last_accessed": int(datetime.now().timestamp()),
        }]

        collection = Collection(self.collection_name)
        collection.insert(memory_data)

        return memory_id

    async def retrieve_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        time_decay: bool = True
    ) -> List[Dict]:
        """检索相关记忆"""
        from pymilvus import Collection

        # 生成查询向量
        query_embedding = await self._get_embedding(query)

        # 向量检索
        collection = Collection(self.collection_name)
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k * 2,  # 过采样
            expr=f'user_id == "{user_id}"'
        )

        # 后处理: 时间衰减 + 重要性加权
        memories = []
        current_time = datetime.now().timestamp()

        for hits in results:
            for hit in hits:
                entity = hit.entity

                # Ebbinghaus遗忘曲线衰减
                time_diff_days = (current_time - entity.get("created_at")) / 86400
                decay_factor = np.exp(-time_diff_days / 30)  # 30天半衰期

                # 访问频率增强
                access_boost = min(entity.get("access_count", 0) * 0.1, 0.5)

                # 综合得分
                score = (
                    (1 - hit.distance) * 0.6 +  # 向量相似度
                    entity.get("importance", 0.5) * 0.2 +  # 重要性
                    (decay_factor if time_decay else 1.0) * 0.1 +  # 时间衰减
                    access_boost * 0.1  # 访问频率
                )

                memories.append({
                    "memory_id": entity.get("memory_id"),
                    "content": entity.get("content"),
                    "memory_type": entity.get("memory_type"),
                    "score": score,
                    "created_at": entity.get("created_at"),
                })

        # 按综合得分排序并返回top_k
        memories.sort(key=lambda x: x["score"], reverse=True)
        return memories[:top_k]

    async def update_memory_access(self, memory_id: str):
        """更新记忆访问统计"""
        from pymilvus import Collection

        collection = Collection(self.collection_name)

        # 增加访问计数和更新访问时间
        # 注意: Milvus不支持原地更新,需要先查询再重新插入
        expr = f'memory_id == "{memory_id}"'
        results = collection.query(expr=expr, output_fields=["*"])

        if results:
            entity = results[0]
            entity["access_count"] += 1
            entity["last_accessed"] = int(datetime.now().timestamp())

            # 删除旧记录
            collection.delete(expr=expr)

            # 插入更新后的记录
            collection.insert([entity])

    async def _get_embedding(self, text: str) -> List[float]:
        """调用Model Adapter获取embedding"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.embedding_service_url}/api/v1/embeddings",
                json={
                    "input": text,
                    "model": "text-embedding-ada-002"
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]


# 集成到 MemoryManager

class MemoryManager:
    def __init__(self):
        self.short_term = {}  # 对话级短期记忆
        self.long_term = VectorMemoryManager()  # 向量化长期记忆

    async def add_to_long_term(
        self,
        user_id: str,
        content: str,
        memory_type: str = "conversation"
    ):
        """添加到长期记忆"""
        # 评估重要性
        importance = await self._evaluate_importance(content)

        await self.long_term.store_memory(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance
        )

    async def recall(
        self,
        user_id: str,
        query: str,
        top_k: int = 3
    ) -> List[str]:
        """回忆相关记忆"""
        memories = await self.long_term.retrieve_memory(
            user_id=user_id,
            query=query,
            top_k=top_k
        )

        # 更新访问统计
        for memory in memories:
            await self.long_term.update_memory_access(memory["memory_id"])

        return [m["content"] for m in memories]

    async def _evaluate_importance(self, content: str) -> float:
        """使用LLM评估记忆重要性"""
        # 简化实现: 基于规则
        # 生产环境应使用LLM评估

        important_keywords = ["重要", "记住", "关键", "必须"]
        score = 0.5

        for keyword in important_keywords:
            if keyword in content:
                score += 0.1

        return min(score, 1.0)
```

**配置更新**:

```yaml
# config/agent-engine.yaml

memory:
  type: 'vector' # "memory" or "vector"
  vector:
    milvus_url: 'http://milvus:19530'
    embedding_service_url: 'http://model-adapter:8002'
    collection_name: 'agent_memory'
    time_decay_enabled: true
    time_decay_half_life_days: 30
```

**验收标准**:

- [ ] 记忆成功存储到 Milvus
- [ ] 向量检索召回率 > 80%
- [ ] 时间衰减机制生效
- [ ] 访问频率统计正确
- [ ] 单次检索延迟 < 300ms

**工作量**: 3-4 天

---

#### 2. 工具注册与实现

**文件**:

- `app/tools/tool_registry.py:246,261,267`
- `app/core/tools/builtin_tools.py:34,65,79`
- `main.py:225`

**问题描述**:

```python
# tool_registry.py:246
# TODO: 实现真实的搜索功能

# tool_registry.py:261
# TODO: 实现真实的知识库搜索

# tool_registry.py:267
# TODO: 实现真实的天气API调用

# builtin_tools.py:34
# TODO: 实际实现搜索功能(调用搜索引擎API)

# main.py:225
# TODO: 实现动态工具注册
```

**影响**: Agent 工具调用都是 Mock，无实际功能

**详细设计方案**:

```python
# app/tools/real_tools.py

from typing import Dict, Any, List
import httpx
import os
from datetime import datetime

class SearchTool:
    """网络搜索工具 (基于SerpAPI)"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.base_url = "https://serpapi.com/search"

    async def execute(self, query: str, num_results: int = 5) -> str:
        """执行搜索"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.base_url,
                params={
                    "q": query,
                    "api_key": self.api_key,
                    "num": num_results,
                    "engine": "google"
                }
            )

            if response.status_code != 200:
                return f"搜索失败: {response.text}"

            data = response.json()
            organic_results = data.get("organic_results", [])

            # 格式化结果
            results = []
            for i, result in enumerate(organic_results[:num_results], 1):
                results.append(
                    f"{i}. {result.get('title')}\n"
                    f"   {result.get('snippet')}\n"
                    f"   URL: {result.get('link')}"
                )

            return "\n\n".join(results) if results else "未找到相关结果"

    def get_definition(self) -> Dict:
        """工具定义"""
        return {
            "name": "search",
            "description": "在互联网上搜索信息。当需要获取实时信息、最新新闻或不在知识库中的内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }


class KnowledgeBaseTool:
    """知识库查询工具"""

    def __init__(self, rag_service_url: str = "http://rag-engine:8006"):
        self.rag_service_url = rag_service_url

    async def execute(
        self,
        query: str,
        knowledge_base_id: str,
        top_k: int = 3
    ) -> str:
        """查询知识库"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.rag_service_url}/api/v1/rag/retrieve",
                json={
                    "query": query,
                    "knowledge_base_id": knowledge_base_id,
                    "top_k": top_k
                }
            )

            if response.status_code != 200:
                return f"知识库查询失败: {response.text}"

            data = response.json()
            documents = data.get("documents", [])

            if not documents:
                return "知识库中未找到相关信息"

            # 格式化结果
            results = []
            for i, doc in enumerate(documents, 1):
                results.append(
                    f"{i}. {doc.get('content')[:200]}...\n"
                    f"   (来源: {doc.get('metadata', {}).get('title', '未知')})"
                )

            return "\n\n".join(results)

    def get_definition(self) -> Dict:
        """工具定义"""
        return {
            "name": "knowledge_base",
            "description": "从企业知识库中检索信息。当需要查询公司文档、政策、产品信息时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询问题"
                    },
                    "knowledge_base_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回文档数量",
                        "default": 3
                    }
                },
                "required": ["query", "knowledge_base_id"]
            }
        }


class WeatherTool:
    """天气查询工具"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    async def execute(self, city: str, country: str = "CN") -> str:
        """查询天气"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.base_url,
                params={
                    "q": f"{city},{country}",
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": "zh_cn"
                }
            )

            if response.status_code != 200:
                return f"天气查询失败: {response.text}"

            data = response.json()

            weather_desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return (
                f"{city}当前天气:\n"
                f"- 天气: {weather_desc}\n"
                f"- 温度: {temp}°C (体感 {feels_like}°C)\n"
                f"- 湿度: {humidity}%\n"
                f"- 风速: {wind_speed} m/s"
            )

    def get_definition(self) -> Dict:
        """工具定义"""
        return {
            "name": "weather",
            "description": "查询指定城市的实时天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称(中文或英文)"
                    },
                    "country": {
                        "type": "string",
                        "description": "国家代码(如CN, US)",
                        "default": "CN"
                    }
                },
                "required": ["city"]
            }
        }


class CalculatorTool:
    """计算器工具"""

    async def execute(self, expression: str) -> str:
        """执行计算"""
        try:
            # 安全的数学表达式求值
            import ast
            import operator as op

            # 支持的运算符
            operators = {
                ast.Add: op.add,
                ast.Sub: op.sub,
                ast.Mult: op.mul,
                ast.Div: op.truediv,
                ast.Pow: op.pow,
                ast.USub: op.neg,
            }

            def eval_expr(node):
                if isinstance(node, ast.Num):
                    return node.n
                elif isinstance(node, ast.BinOp):
                    return operators[type(node.op)](
                        eval_expr(node.left),
                        eval_expr(node.right)
                    )
                elif isinstance(node, ast.UnaryOp):
                    return operators[type(node.op)](eval_expr(node.operand))
                else:
                    raise ValueError(f"不支持的表达式: {node}")

            node = ast.parse(expression, mode='eval')
            result = eval_expr(node.body)

            return f"{expression} = {result}"

        except Exception as e:
            return f"计算错误: {str(e)}"

    def get_definition(self) -> Dict:
        """工具定义"""
        return {
            "name": "calculator",
            "description": "执行数学计算。支持加减乘除和幂运算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'"
                    }
                },
                "required": ["expression"]
            }
        }


# 动态工具注册系统

class DynamicToolRegistry:
    """动态工具注册表"""

    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self._init_builtin_tools()

    def _init_builtin_tools(self):
        """初始化内置工具"""
        self.register(SearchTool())
        self.register(KnowledgeBaseTool())
        self.register(WeatherTool())
        self.register(CalculatorTool())

    def register(self, tool_instance: Any):
        """注册工具"""
        definition = tool_instance.get_definition()
        tool_name = definition["name"]

        self.tools[tool_name] = {
            "instance": tool_instance,
            "definition": definition
        }

        print(f"✅ 工具已注册: {tool_name}")

    def unregister(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]
            print(f"❌ 工具已注销: {tool_name}")

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> str:
        """执行工具"""
        if tool_name not in self.tools:
            raise ValueError(f"工具不存在: {tool_name}")

        tool_instance = self.tools[tool_name]["instance"]
        return await tool_instance.execute(**parameters)

    def list_tools(self) -> List[Dict]:
        """列出所有工具"""
        return [
            tool["definition"]
            for tool in self.tools.values()
        ]

    def get_tool_definitions_for_llm(self) -> List[Dict]:
        """获取OpenAI function calling格式的工具定义"""
        return [
            {
                "type": "function",
                "function": tool["definition"]
            }
            for tool in self.tools.values()
        ]


# 更新 main.py 启动代码

@app.on_event("startup")
async def startup_event():
    """应用启动"""
    print("🚀 Agent Engine starting...")

    # 初始化动态工具注册表
    app.state.tool_registry = DynamicToolRegistry()

    # 可选: 从配置文件加载自定义工具
    # await load_custom_tools(app.state.tool_registry)

    print(f"✅ Loaded {len(app.state.tool_registry.tools)} tools")
    print("✅ Agent Engine started successfully")


# 工具API端点

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

class ToolExecuteRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

class ToolExecuteResponse(BaseModel):
    result: str
    execution_time: float

@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """执行工具"""
    import time

    start_time = time.time()

    try:
        result = await app.state.tool_registry.execute_tool(
            tool_name=request.tool_name,
            parameters=request.parameters
        )

        execution_time = time.time() - start_time

        return ToolExecuteResponse(
            result=result,
            execution_time=execution_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_tools():
    """列出所有可用工具"""
    return {
        "tools": app.state.tool_registry.list_tools(),
        "count": len(app.state.tool_registry.tools)
    }


@router.post("/register")
async def register_custom_tool(tool_definition: Dict):
    """注册自定义工具 (高级功能)"""
    # 从工具定义动态创建工具实例
    # 生产环境需要严格的安全验证
    raise HTTPException(status_code=501, detail="Custom tool registration not implemented")
```

**环境变量**:

```bash
# .env

# 工具API密钥
SERPAPI_KEY=your_serpapi_key
OPENWEATHER_API_KEY=your_openweather_key

# 服务地址
RAG_SERVICE_URL=http://rag-engine:8006
```

**验收标准**:

- [ ] 搜索工具返回真实搜索结果
- [ ] 知识库工具成功调用 RAG 服务
- [ ] 天气工具返回实时天气数据
- [ ] 计算器工具正确计算表达式
- [ ] 动态工具注册/注销功能正常
- [ ] 工具执行延迟 < 5s

**工作量**: 3-4 天

---

#### 3. Plan-Execute 执行器

**文件**: `app/core/executor/plan_execute_executor.py:97`

**问题描述**:

```python
# TODO: 实际应该解析步骤，调用工具
```

**影响**: 无法处理复杂的多步骤任务

**详细设计方案**:

````python
# app/core/executor/plan_execute_executor.py (完整实现)

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import json
import asyncio

class ExecutionStep(BaseModel):
    """执行步骤"""
    step_id: int
    description: str
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None


class ExecutionPlan(BaseModel):
    """执行计划"""
    task: str
    steps: List[ExecutionStep]
    status: str = "created"
    current_step: int = 0


class PlanExecuteExecutor:
    """Plan-and-Execute 执行器"""

    def __init__(
        self,
        llm_service,
        tool_registry,
        max_retries: int = 2
    ):
        self.llm_service = llm_service
        self.tool_registry = tool_registry
        self.max_retries = max_retries

    async def execute(
        self,
        task: str,
        context: Dict = None
    ) -> Dict[str, Any]:
        """执行完整的Plan-Execute流程"""

        # Phase 1: Planning - 生成执行计划
        plan = await self._generate_plan(task, context)

        # Phase 2: Execution - 逐步执行
        execution_log = []

        for i, step in enumerate(plan.steps):
            print(f"\n📋 执行步骤 {i+1}/{len(plan.steps)}: {step.description}")

            step.status = "running"
            plan.current_step = i

            try:
                # 执行步骤
                result = await self._execute_step(step, execution_log)

                step.status = "completed"
                step.result = result

                execution_log.append({
                    "step_id": step.step_id,
                    "description": step.description,
                    "result": result,
                    "status": "completed"
                })

                print(f"✅ 步骤完成: {result[:100]}...")

            except Exception as e:
                step.status = "failed"
                step.error = str(e)

                execution_log.append({
                    "step_id": step.step_id,
                    "description": step.description,
                    "error": str(e),
                    "status": "failed"
                })

                print(f"❌ 步骤失败: {str(e)}")

                # 尝试修复或跳过
                retry_success = await self._handle_failure(step, execution_log)

                if not retry_success:
                    # 致命失败，中止执行
                    break

        # Phase 3: Synthesis - 综合最终答案
        final_answer = await self._synthesize_answer(task, execution_log)

        return {
            "task": task,
            "plan": plan.dict(),
            "execution_log": execution_log,
            "final_answer": final_answer,
            "status": "completed" if all(s.status == "completed" for s in plan.steps) else "partial"
        }

    async def _generate_plan(
        self,
        task: str,
        context: Dict = None
    ) -> ExecutionPlan:
        """使用LLM生成执行计划"""

        # 获取可用工具
        tools = self.tool_registry.list_tools()
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools
        ])

        system_prompt = f"""你是一个任务规划助手。给定一个任务，你需要将其分解为可执行的步骤。

可用工具:
{tools_desc}

请生成一个JSON格式的执行计划，包含以下字段:
{{
    "steps": [
        {{
            "step_id": 1,
            "description": "步骤描述",
            "tool_name": "工具名称(可选)",
            "parameters": {{"param1": "value1"}}
        }}
    ]
}}

规则:
1. 每个步骤应该清晰、可执行
2. 如果需要调用工具，指定tool_name和parameters
3. 步骤之间应该有逻辑顺序
4. 最后一步通常是综合所有信息回答问题
"""

        user_prompt = f"""任务: {task}

{f"上下文: {context}" if context else ""}

请生成执行计划:"""

        # 调用LLM
        response = await self.llm_service.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4",
            temperature=0.1
        )

        # 解析计划
        try:
            plan_json = self._extract_json(response["choices"][0]["message"]["content"])
            steps = [ExecutionStep(**step) for step in plan_json["steps"]]

            return ExecutionPlan(task=task, steps=steps)

        except Exception as e:
            # 回退: 使用默认单步计划
            print(f"⚠️  计划解析失败，使用回退计划: {e}")
            return ExecutionPlan(
                task=task,
                steps=[
                    ExecutionStep(
                        step_id=1,
                        description=f"直接回答: {task}",
                        tool_name=None
                    )
                ]
            )

    async def _execute_step(
        self,
        step: ExecutionStep,
        execution_log: List[Dict]
    ) -> str:
        """执行单个步骤"""

        if step.tool_name:
            # 工具调用
            return await self.tool_registry.execute_tool(
                tool_name=step.tool_name,
                parameters=step.parameters or {}
            )
        else:
            # LLM推理
            return await self._llm_reasoning(step, execution_log)

    async def _llm_reasoning(
        self,
        step: ExecutionStep,
        execution_log: List[Dict]
    ) -> str:
        """使用LLM进行推理"""

        # 构建上下文
        context = "\n".join([
            f"步骤 {log['step_id']}: {log['description']}\n结果: {log.get('result', '失败')}"
            for log in execution_log
        ])

        prompt = f"""基于以下已执行步骤的结果:

{context}

请执行: {step.description}"""

        response = await self.llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4",
            temperature=0.7
        )

        return response["choices"][0]["message"]["content"]

    async def _handle_failure(
        self,
        step: ExecutionStep,
        execution_log: List[Dict]
    ) -> bool:
        """处理步骤失败"""

        if step.tool_name:
            # 工具调用失败，尝试用LLM替代
            print(f"🔄 尝试用LLM替代工具: {step.tool_name}")

            try:
                result = await self._llm_reasoning(step, execution_log)
                step.status = "completed"
                step.result = result

                execution_log[-1]["status"] = "recovered"
                execution_log[-1]["result"] = result

                return True
            except Exception as e:
                print(f"❌ 恢复失败: {e}")
                return False

        return False

    async def _synthesize_answer(
        self,
        task: str,
        execution_log: List[Dict]
    ) -> str:
        """综合最终答案"""

        context = "\n\n".join([
            f"步骤 {log['step_id']}: {log['description']}\n"
            f"状态: {log['status']}\n"
            f"结果: {log.get('result', log.get('error', '未执行'))}"
            for log in execution_log
        ])

        prompt = f"""原始任务: {task}

执行过程:
{context}

基于以上执行过程，请综合生成最终答案。要求:
1. 直接回答用户的问题
2. 整合所有步骤的有效信息
3. 如果有步骤失败，说明原因但不影响整体回答
4. 保持简洁清晰"""

        response = await self.llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4",
            temperature=0.7
        )

        return response["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except:
            pass

        # 尝试提取```json```代码块
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # 尝试提取第一个JSON对象
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("无法从响应中提取JSON")


# 示例使用

async def example_usage():
    """示例: 使用Plan-Execute执行复杂任务"""

    executor = PlanExecuteExecutor(
        llm_service=llm_service,
        tool_registry=tool_registry
    )

    task = "帮我查一下明天北京的天气，并且搜索一下北京最近有什么好玩的地方"

    result = await executor.execute(task)

    print("\n" + "="*80)
    print("📋 执行计划:")
    for step in result["plan"]["steps"]:
        print(f"  {step['step_id']}. {step['description']}")

    print("\n" + "="*80)
    print("📝 执行日志:")
    for log in result["execution_log"]:
        print(f"  [{log['status']}] {log['description']}")
        if log.get('result'):
            print(f"    → {log['result'][:100]}...")

    print("\n" + "="*80)
    print("🎯 最终答案:")
    print(result["final_answer"])
````

**API 集成**:

```python
# app/routers/agent.py

@router.post("/execute/plan")
async def execute_with_plan(request: AgentTaskRequest):
    """使用Plan-Execute模式执行任务"""

    executor = PlanExecuteExecutor(
        llm_service=app.state.llm_service,
        tool_registry=app.state.tool_registry
    )

    result = await executor.execute(
        task=request.task,
        context=request.context
    )

    return result
```

**验收标准**:

- [ ] 能正确分解复杂任务
- [ ] 步骤按顺序正确执行
- [ ] 步骤失败时能恢复或跳过
- [ ] 最终答案综合所有信息
- [ ] 执行日志完整可追溯

**工作量**: 3-4 天

---

#### 4. 流式输出

**文件**: `app/workflows/react_agent.py:385`

**问题描述**:

```python
# TODO: 实现流式输出
```

**影响**: 无法实时查看 Agent 推理过程

**详细设计方案**:

```python
# app/services/agent_service.py

from typing import AsyncIterator
import json

class AgentService:

    async def execute_stream(
        self,
        task: AgentTask
    ) -> AsyncIterator[str]:
        """流式执行Agent任务"""

        # 初始化
        yield self._format_sse({
            "type": "start",
            "task_id": task.task_id,
            "task": task.task
        })

        # ReAct循环
        iteration = 0
        max_iterations = task.max_iterations or 10

        while iteration < max_iterations:
            iteration += 1

            # 1. Thought - 思考
            yield self._format_sse({
                "type": "thought",
                "iteration": iteration,
                "stage": "thinking"
            })

            thought_response = await self._llm_think(task, iteration)
            thought = self._extract_thought(thought_response)

            yield self._format_sse({
                "type": "thought",
                "iteration": iteration,
                "content": thought
            })

            # 2. 判断是否为最终答案
            if self._is_final_answer(thought_response):
                final_answer = self._extract_final_answer(thought_response)

                yield self._format_sse({
                    "type": "final_answer",
                    "content": final_answer,
                    "iterations": iteration
                })

                yield self._format_sse({
                    "type": "complete",
                    "status": "success"
                })

                return

            # 3. Action - 行动
            action = self._extract_action(thought_response)

            yield self._format_sse({
                "type": "action",
                "iteration": iteration,
                "tool_name": action["tool"],
                "parameters": action["input"]
            })

            # 4. Observation - 观察
            try:
                observation = await self._execute_action(action)

                yield self._format_sse({
                    "type": "observation",
                    "iteration": iteration,
                    "content": observation
                })

            except Exception as e:
                yield self._format_sse({
                    "type": "error",
                    "iteration": iteration,
                    "error": str(e)
                })

                yield self._format_sse({
                    "type": "complete",
                    "status": "error"
                })

                return

        # 超时
        yield self._format_sse({
            "type": "timeout",
            "iterations": max_iterations
        })

        yield self._format_sse({
            "type": "complete",
            "status": "timeout"
        })

    def _format_sse(self, data: dict) -> str:
        """格式化SSE消息"""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    # ... 其他辅助方法


# app/routers/agent.py

from fastapi.responses import StreamingResponse

@router.post("/execute/stream")
async def execute_agent_stream(request: AgentTaskRequest):
    """流式执行Agent (SSE)"""

    task = AgentTask(
        task_id=str(uuid.uuid4()),
        task=request.task,
        context=request.context,
        max_iterations=request.max_iterations
    )

    return StreamingResponse(
        agent_service.execute_stream(task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
    )
```

**前端集成示例**:

```javascript
// React 前端示例

const useAgentStream = (task) => {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('idle');

  const execute = async () => {
    setStatus('running');
    setEvents([]);

    const response = await fetch('/api/v1/agent/execute/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ task }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));

          setEvents((prev) => [...prev, data]);

          if (data.type === 'complete') {
            setStatus(data.status);
          }
        }
      }
    }
  };

  return { events, status, execute };
};

// 使用
function AgentDebugPanel() {
  const { events, status, execute } = useAgentStream();

  return (
    <div>
      <button onClick={() => execute('查询明天北京天气')}>执行</button>

      <div className="timeline">
        {events.map((event, i) => (
          <div key={i} className={`event event-${event.type}`}>
            {event.type === 'thought' && <div>💭 思考: {event.content}</div>}
            {event.type === 'action' && <div>⚡ 行动: {event.tool_name}</div>}
            {event.type === 'observation' && <div>👁️ 观察: {event.content}</div>}
            {event.type === 'final_answer' && <div>✅ 答案: {event.content}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**验收标准**:

- [ ] SSE 连接稳定不断开
- [ ] 事件实时推送延迟 < 100ms
- [ ] 所有事件类型正确推送
- [ ] 前端能正确解析和显示
- [ ] 错误场景能优雅处理

**工作量**: 2-3 天

---

#### 5. Agent 路由逻辑

**文件**: `routers/agent.py:34,53`

**问题描述**:

```python
# TODO: 实际实现搜索功能（调用搜索引擎API）
# TODO: Implement agent execution logic using LangGraph
# TODO: Implement status retrieval
```

**影响**: Agent 路由和状态查询未实现

**详细设计方案**:

```python
# routers/agent.py (完整实现)

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])

# 任务存储 (生产环境应使用Redis)
task_store = {}

@router.post("/execute", response_model=AgentResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks
):
    """同步执行Agent任务"""

    task_id = str(uuid.uuid4())

    # 创建任务记录
    task_store[task_id] = {
        "task_id": task_id,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "request": request.dict()
    }

    try:
        # 根据策略选择执行器
        if request.strategy == "react":
            executor = ReactExecutor(...)
        elif request.strategy == "plan_execute":
            executor = PlanExecuteExecutor(...)
        else:
            raise HTTPException(400, f"不支持的策略: {request.strategy}")

        # 执行
        result = await executor.execute(
            task=request.task,
            context=request.context
        )

        # 更新任务记录
        task_store[task_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat()
        })

        return AgentResponse(
            task_id=task_id,
            status="completed",
            result=result["final_answer"],
            steps=result.get("execution_log", []),
            metadata={
                "strategy": request.strategy,
                "iterations": result.get("iterations", 0),
                "execution_time": result.get("execution_time", 0)
            }
        )

    except Exception as e:
        task_store[task_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

        raise HTTPException(500, str(e))


@router.post("/execute-async")
async def execute_agent_async(
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks
):
    """异步执行Agent任务"""

    task_id = str(uuid.uuid4())

    # 创建任务记录
    task_store[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "request": request.dict()
    }

    # 添加后台任务
    background_tasks.add_task(
        _execute_agent_background,
        task_id=task_id,
        request=request
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "任务已提交，请使用task_id查询结果"
    }


async def _execute_agent_background(task_id: str, request: AgentExecuteRequest):
    """后台执行Agent"""

    task_store[task_id]["status"] = "running"
    task_store[task_id]["started_at"] = datetime.now().isoformat()

    try:
        # 选择执行器
        if request.strategy == "react":
            executor = ReactExecutor(...)
        elif request.strategy == "plan_execute":
            executor = PlanExecuteExecutor(...)
        else:
            raise ValueError(f"不支持的策略: {request.strategy}")

        # 执行
        result = await executor.execute(
            task=request.task,
            context=request.context
        )

        # 更新结果
        task_store[task_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat()
        })

    except Exception as e:
        task_store[task_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""

    if task_id not in task_store:
        raise HTTPException(404, "任务不存在")

    task = task_store[task_id]

    response = {
        "task_id": task_id,
        "status": task["status"],
        "created_at": task["created_at"]
    }

    if task["status"] == "completed":
        response["result"] = task["result"]
        response["completed_at"] = task.get("completed_at")

    elif task["status"] == "failed":
        response["error"] = task.get("error")
        response["failed_at"] = task.get("failed_at")

    elif task["status"] == "running":
        response["started_at"] = task.get("started_at")
        # 可选: 返回中间进度
        response["progress"] = task.get("progress", {})

    return response


@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """取消任务"""

    if task_id not in task_store:
        raise HTTPException(404, "任务不存在")

    task = task_store[task_id]

    if task["status"] in ["completed", "failed"]:
        raise HTTPException(400, "任务已结束，无法取消")

    # 标记为取消
    task_store[task_id]["status"] = "cancelled"
    task_store[task_id]["cancelled_at"] = datetime.now().isoformat()

    return {"message": "任务已取消"}


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """列出任务"""

    tasks = list(task_store.values())

    # 过滤状态
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # 排序 (最新的在前)
    tasks.sort(key=lambda x: x["created_at"], reverse=True)

    # 分页
    total = len(tasks)
    tasks = tasks[offset:offset+limit]

    return {
        "tasks": tasks,
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

**Redis 持久化版本**:

```python
# app/infrastructure/task_store.py

import redis
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta

class RedisTaskStore:
    """基于Redis的任务存储"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl_days = 7  # 任务保留7天

    def save_task(self, task_id: str, task_data: Dict):
        """保存任务"""
        key = f"agent:task:{task_id}"

        self.redis.setex(
            key,
            timedelta(days=self.ttl_days),
            json.dumps(task_data, ensure_ascii=False)
        )

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务"""
        key = f"agent:task:{task_id}"
        data = self.redis.get(key)

        return json.loads(data) if data else None

    def update_task(self, task_id: str, updates: Dict):
        """更新任务"""
        task = self.get_task(task_id)
        if task:
            task.update(updates)
            self.save_task(task_id, task)

    def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """列出任务"""
        # 扫描所有任务key
        keys = self.redis.keys("agent:task:*")

        tasks = []
        for key in keys:
            data = self.redis.get(key)
            if data:
                task = json.loads(data)
                if not status or task.get("status") == status:
                    tasks.append(task)

        # 排序并限制数量
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return tasks[:limit]

    def delete_task(self, task_id: str):
        """删除任务"""
        key = f"agent:task:{task_id}"
        self.redis.delete(key)


# 在 main.py 中初始化

@app.on_event("startup")
async def startup_event():
    app.state.task_store = RedisTaskStore(
        redis_url=settings.REDIS_URL
    )
```

**验收标准**:

- [ ] 同步执行返回完整结果
- [ ] 异步执行正确入队
- [ ] 任务状态查询准确
- [ ] 任务列表分页正常
- [ ] 任务取消功能生效
- [ ] Redis 持久化不丢数据

**工作量**: 2-3 天

---

### P1 级别 (重要功能)

#### 6. LangGraph 高级工作流

**建议新增功能** (参考业界最佳实践)

**功能描述**: 使用 LangGraph 构建更复杂的 Agent 工作流

**技术方案**:

```python
# app/workflows/langgraph_workflow.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
import operator

class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[Sequence[str], operator.add]
    task: str
    plan: dict
    current_step: int
    observations: list
    final_answer: str

def plan_node(state: AgentState):
    """规划节点"""
    # 生成执行计划
    plan = generate_plan(state["task"])
    return {"plan": plan, "current_step": 0}

def execute_node(state: AgentState):
    """执行节点"""
    step = state["plan"]["steps"][state["current_step"]]
    observation = execute_step(step)

    return {
        "observations": state["observations"] + [observation],
        "current_step": state["current_step"] + 1
    }

def should_continue(state: AgentState):
    """判断是否继续"""
    if state["current_step"] >= len(state["plan"]["steps"]):
        return "synthesize"
    else:
        return "execute"

def synthesize_node(state: AgentState):
    """综合答案节点"""
    final_answer = synthesize_answer(
        task=state["task"],
        observations=state["observations"]
    )
    return {"final_answer": final_answer}

# 构建图
workflow = StateGraph(AgentState)

workflow.add_node("plan", plan_node)
workflow.add_node("execute", execute_node)
workflow.add_node("synthesize", synthesize_node)

workflow.set_entry_point("plan")
workflow.add_edge("plan", "execute")
workflow.add_conditional_edges(
    "execute",
    should_continue,
    {
        "execute": "execute",
        "synthesize": "synthesize"
    }
)
workflow.add_edge("synthesize", END)

app_workflow = workflow.compile()
```

**工作量**: 4-5 天

---

## 📈 后续迭代计划

### Sprint 1: 核心功能补全 (Week 1-2)

#### 目标

完成 P0 阻塞性功能，使 Agent 具备实际可用性

#### 任务清单

| 任务                | 优先级 | 工作量 | 负责人        | 状态      |
| ------------------- | ------ | ------ | ------------- | --------- |
| 记忆系统 - 向量检索 | P0     | 3-4 天 | AI Engineer 1 | 📝 待开始 |
| 工具注册与实现      | P0     | 3-4 天 | AI Engineer 2 | 📝 待开始 |
| Plan-Execute 执行器 | P0     | 3-4 天 | AI Engineer 1 | 📝 待开始 |

#### 验收标准

- [ ] 记忆系统召回率 > 80%
- [ ] 至少 5 个实际工具可用
- [ ] Plan-Execute 能正确分解任务

---

### Sprint 2: 用户体验提升 (Week 3-4)

#### 目标

优化交互体验，增强可观测性

#### 任务清单

| 任务             | 优先级 | 工作量 | 负责人           | 状态      |
| ---------------- | ------ | ------ | ---------------- | --------- |
| 流式输出         | P0     | 2-3 天 | Backend Engineer | 📝 待开始 |
| Agent 路由逻辑   | P0     | 2-3 天 | Backend Engineer | 📝 待开始 |
| Redis 任务持久化 | P1     | 2 天   | Backend Engineer | 📝 待开始 |

#### 验收标准

- [ ] SSE 流式输出稳定
- [ ] 任务状态查询准确
- [ ] Redis 持久化不丢数据

---

### Sprint 3: 高级能力建设 (Week 5-6)

#### 目标

增加高级推理能力和工具生态

#### 任务清单

| 任务               | 优先级 | 工作量 | 负责人          | 状态      |
| ------------------ | ------ | ------ | --------------- | --------- |
| LangGraph 工作流   | P1     | 4-5 天 | AI Engineer 1   | 📝 待开始 |
| 自定义工具插件系统 | P2     | 3 天   | AI Engineer 2   | 📝 待开始 |
| 多 Agent 协作      | P2     | 5-7 天 | AI Engineer 1+2 | 📝 待开始 |

#### 验收标准

- [ ] LangGraph 工作流可正常运行
- [ ] 支持用户自定义工具注册
- [ ] 多 Agent 能协同完成任务

---

## 🎯 业界对比与最佳实践

### 与 LangChain/AutoGPT/BabyAGI 对比

| 功能           | 当前实现     | LangChain | AutoGPT   | 本项目目标         |
| -------------- | ------------ | --------- | --------- | ------------------ |
| ReAct Agent    | ✅ 已实现    | ✅        | ✅        | ✅                 |
| Plan & Execute | ⚠️ 部分完成  | ✅        | ✅        | ✅ 完善            |
| 工具生态       | ⚠️ 3 个 Mock | ✅ 50+    | ✅ 20+    | ✅ 10+ 实际工具    |
| 记忆系统       | ❌ Mock      | ✅ 向量化 | ✅ 向量化 | ✅ 向量化+时间衰减 |
| 流式输出       | ❌           | ✅        | ❌        | ✅                 |
| 多 Agent 协作  | ❌           | ✅        | ✅        | ✅ (Sprint 3)      |
| 自学习         | ❌           | ⚠️ 部分   | ✅        | 📋 规划中          |

### 借鉴的最佳实践

1. **LangChain**

   - 工具定义标准化 (OpenAI Function Calling 格式)
   - 记忆系统设计 (短期 + 长期)
   - Agent 执行器抽象

2. **AutoGPT**

   - Plan-and-Execute 模式
   - 自主目标分解
   - 持续记忆管理

3. **ChatDev/MetaGPT**
   - 多 Agent 协作模式
   - 角色扮演机制

---

## 📊 成功指标 (KPI)

| 指标         | 当前     | 目标 (Sprint 1) | 目标 (Sprint 3) |
| ------------ | -------- | --------------- | --------------- |
| 工具数量     | 3 (Mock) | 5+ (实际)       | 10+ (实际)      |
| 记忆召回率   | N/A      | > 80%           | > 90%           |
| 任务成功率   | ~40%     | > 70%           | > 85%           |
| 平均执行时间 | ~10s     | < 8s            | < 5s            |
| 用户满意度   | N/A      | > 4.0/5.0       | > 4.5/5.0       |

---

## 🛠️ 开发指南

### 本地开发

```bash
# 1. 安装依赖
cd algo/agent-engine
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 3. 启动服务
uvicorn main:app --reload --port 8003

# 4. 访问文档
open http://localhost:8003/docs
```

### 测试

```bash
# 单元测试
pytest tests/unit/ -v

# 集成测试
pytest tests/integration/ -v

# 覆盖率
pytest --cov=app tests/
```

### Docker 部署

```bash
# 构建镜像
docker build -t agent-engine:v2.0 .

# 运行容器
docker run -p 8003:8003 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e REDIS_URL=redis://redis:6379/0 \
  agent-engine:v2.0
```

---

## 📝 相关文档

- [Agent Engine README](algo/agent-engine/README.md)
- [Agent Engine 实现总结](algo/agent-engine/IMPLEMENTATION_SUMMARY.md)
- [API 文档](http://localhost:8003/docs)
- [架构设计](docs/arch/agent-engine.md)

---

## 📞 联系方式

- **负责人**: AI Team Lead
- **开发团队**: AI Engineer 1, AI Engineer 2
- **Slack**: #agent-engine-dev
- **Wiki**: [Agent Engine Wiki](link)

---

**文档版本**: v1.0.0
**最后更新**: 2025-10-27
**下次更新**: Sprint 1 结束后 (Week 2)
