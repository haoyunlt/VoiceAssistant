# VoiceHelper-99-实战示例与最佳实践

## 文档概述

本文档提供 VoiceHelper 平台的**实战示例、开发经验、部署最佳实践、性能优化技巧**，帮助开发者快速上手并掌握系统的核心能力。

---

## 目录

1. [快速开始示例](#1-快速开始示例)
2. [核心功能实战](#2-核心功能实战)
3. [微服务开发最佳实践](#3-微服务开发最佳实践)
4. [AI服务集成案例](#4-ai服务集成案例)
5. [性能优化实战](#5-性能优化实战)
6. [故障处理与监控](#6-故障处理与监控)
7. [生产部署经验](#7-生产部署经验)
8. [常见问题与解决方案](#8-常见问题与解决方案)

---

## 1. 快速开始示例

### 1.1 本地开发环境搭建

#### 前置条件

```bash
# 检查必需工具
go version    # 1.21+
python --version    # 3.11+
docker --version    # 20.10+
kubectl version    # 1.25+
```

#### 一键启动基础设施

```bash
# 1. 克隆项目
git clone https://github.com/haoyunlt/VoiceHelper.git
cd VoiceHelper

# 2. 启动基础设施（Docker Compose）
cd docker/observability
docker-compose up -d

# 检查服务状态
docker-compose ps

# 应看到以下服务运行：
# - postgres (5432)
# - redis (6379)
# - milvus (19530)
# - elasticsearch (9200)
# - prometheus (9090)
# - grafana (3000)
# - jaeger (16686)
```

#### 启动Go服务（Identity Service示例）

```bash
cd cmd/identity-service

# 1. 创建配置文件
cp ../../configs/app/identity-service.yaml.example ./config.yaml

# 2. 修改配置（连接本地数据库）
cat > config.yaml << EOF
server:
  http:
    addr: :8000
  grpc:
    addr: :9000

data:
  database:
    driver: postgres
    source: "host=localhost port=5432 user=postgres password=postgres dbname=voicehelper sslmode=disable"
  redis:
    addr: localhost:6379
    password: ""
    db: 0

auth:
  jwt_secret: "your-secret-key-change-this-in-production"
  access_token_expiry: "1h"
  refresh_token_expiry: "168h"
EOF

# 3. 运行数据库迁移
go run main.go migrate

# 4. 启动服务
go run main.go -conf ./config.yaml

# 5. 验证服务
curl http://localhost:8000/health
# 应返回: {"status":"healthy"}
```

#### 启动Python服务（RAG Engine示例）

```bash
cd algo/rag-engine

# 1. 创建虚拟环境（使用清华镜像）
python3.11 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量
cat > .env << EOF
OPENAI_API_KEY=sk-your-api-key
REDIS_HOST=localhost
REDIS_PORT=6379
MILVUS_HOST=localhost
MILVUS_PORT=19530
EOF

# 4. 启动服务
python main.py

# 5. 验证服务
curl http://localhost:8006/health
# 应返回: {"status":"healthy","service":"rag-engine"}

# 6. 访问API文档
open http://localhost:8006/docs
```

### 1.2 第一个API调用

#### 用户注册与登录

```bash
# 1. 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "username": "testuser"
  }'

# 响应示例
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "testuser",
  "created_at": "2025-11-01T10:00:00Z"
}

# 2. 用户登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'

# 响应示例（保存access_token）
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "testuser"
  }
}

# 3. 设置Token为环境变量（后续请求使用）
export ACCESS_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 创建对话并发送消息

```bash
# 1. 创建对话
curl -X POST http://localhost:8001/api/v1/conversations \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "技术咨询"
  }'

# 响应示例
{
  "id": "conv-123456",
  "title": "技术咨询",
  "created_at": "2025-11-01T10:05:00Z"
}

# 2. 发送消息（触发AI回复）
curl -X POST http://localhost:8001/api/v1/conversations/conv-123456/messages \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "什么是RAG技术？"
  }'

# 响应示例
{
  "id": "msg-789",
  "conversation_id": "conv-123456",
  "role": "assistant",
  "content": "RAG（Retrieval-Augmented Generation）是一种检索增强生成技术...",
  "sources": [
    {"title": "RAG技术白皮书", "url": "https://..."}
  ],
  "created_at": "2025-11-01T10:06:00Z"
}
```

---

## 2. 核心功能实战

### 2.1 RAG检索增强生成完整流程

#### 场景：构建企业知识库问答系统

**步骤1：上传文档并索引**

```bash
# 1. 创建知识库
curl -X POST http://localhost:8002/api/v1/knowledge/bases \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "product_manual",
    "display_name": "产品使用手册",
    "description": "公司产品的完整使用说明"
  }'

# 响应
{
  "id": "kb-001",
  "name": "product_manual",
  "status": "active"
}

# 2. 上传PDF文档
curl -X POST http://localhost:8002/api/v1/knowledge/bases/kb-001/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@./product_manual.pdf" \
  -F "metadata={\"category\":\"manual\",\"version\":\"v2.0\"}"

# 响应
{
  "document_id": "doc-001",
  "status": "processing",
  "message": "文档正在处理中，预计需要2-5分钟"
}

# 3. 轮询文档处理状态
curl http://localhost:8002/api/v1/knowledge/documents/doc-001/status \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 响应（处理完成）
{
  "document_id": "doc-001",
  "status": "indexed",
  "chunk_count": 120,
  "vector_count": 120,
  "processing_time": "2m15s"
}
```

**步骤2：执行RAG查询**

```python
# Python客户端示例
import requests

# 配置
BASE_URL = "http://localhost:8006"
ACCESS_TOKEN = "your_access_token"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# RAG查询请求
payload = {
    "query": "如何重置产品密码？",
    "kb_id": "kb-001",
    "mode": "ultimate",  # 使用终极RAG模式（所有优化）
    "top_k": 5,
    "use_cache": True,
    "use_rerank": True,
    "use_graph": False,  # 简单查询无需图谱
    "use_self_rag": True,  # 启用幻觉检测
    "use_compression": True,  # 启用上下文压缩
    "compression_ratio": 0.5
}

response = requests.post(
    f"{BASE_URL}/api/v1/rag/query",
    headers=headers,
    json=payload
)

result = response.json()

# 解析响应
print("答案:", result["answer"])
print("\n引用来源:")
for source in result["sources"]:
    print(f"  - {source['title']} (相关度: {source['score']:.2f})")
    print(f"    {source['content'][:100]}...")

print("\n性能指标:")
print(f"  检索延迟: {result['metrics']['retrieval_latency']:.2f}s")
print(f"  生成延迟: {result['metrics']['generation_latency']:.2f}s")
print(f"  总延迟: {result['metrics']['total_latency']:.2f}s")
print(f"  Token消耗: {result['metrics']['tokens_used']}")
print(f"  成本: ${result['metrics']['cost_usd']:.4f}")

print("\n启用的功能:")
for feature in result["features_used"]:
    print(f"  ✅ {feature}")
```

**响应示例**：

```json
{
  "answer": "重置产品密码的步骤如下：\n1. 登录产品管理后台\n2. 进入"设置" -> "账户管理"\n3. 点击"修改密码"按钮\n4. 输入当前密码和新密码（需满足8位+大小写+数字）\n5. 点击"确认"保存\n\n如果忘记当前密码，请联系管理员重置。",
  "sources": [
    {
      "document_id": "doc-001",
      "chunk_id": "chunk-45",
      "title": "产品使用手册 - 第5章 账户管理",
      "content": "5.2 密码管理\n用户可以随时修改密码。修改密码的步骤：...",
      "score": 0.92,
      "page": 45
    },
    {
      "document_id": "doc-001",
      "chunk_id": "chunk-12",
      "title": "产品使用手册 - 第2章 安全设置",
      "content": "2.3 密码策略\n密码必须满足以下要求：最少8位，包含大写、小写字母和数字...",
      "score": 0.85,
      "page": 12
    }
  ],
  "metrics": {
    "retrieval_latency": 0.45,
    "rerank_latency": 0.30,
    "generation_latency": 1.20,
    "total_latency": 1.95,
    "tokens_used": 1850,
    "cost_usd": 0.0037,
    "cache_hit": false,
    "compression_applied": true,
    "self_rag_triggered": false
  },
  "features_used": [
    "hybrid_retrieval",
    "cross_encoder_rerank",
    "context_compression",
    "self_rag_verification"
  ],
  "query_classifier": {
    "type": "factual",
    "complexity": "simple",
    "strategy": "hybrid_retrieval"
  }
}
```

### 2.2 Agent智能任务执行

#### 场景：复杂多步骤任务自动化

**示例：市场分析报告生成**

```python
import requests

# Agent执行请求
payload = {
    "task": "分析2024年Q4人工智能市场趋势，包括主要玩家、市场规模、增长预测",
    "mode": "plan_execute",  # 使用Plan-Execute模式
    "tools": [
        "web_search",      # 网络搜索
        "calculator",      # 计算器
        "knowledge_base"   # 知识库查询
    ],
    "max_steps": 15,
    "enable_reflection": True,  # 启用自我反思
    "user_id": "user-123",
    "session_id": "session-456"
}

response = requests.post(
    "http://localhost:8010/api/v1/agent/execute",
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    json=payload,
    timeout=120
)

result = response.json()

# 输出执行过程
print("任务分解:")
for i, step in enumerate(result["plan"], 1):
    print(f"{i}. {step['description']}")

print("\n执行追踪:")
for i, trace in enumerate(result["execution_trace"], 1):
    print(f"\n步骤 {i}: {trace['step_type']}")
    print(f"  思考: {trace['thought']}")
    print(f"  动作: {trace['action']}")
    if 'tool_result' in trace:
        print(f"  结果: {trace['tool_result'][:100]}...")

print("\n最终结果:")
print(result["final_result"])

print("\n性能统计:")
print(f"  总步骤: {result['stats']['total_steps']}")
print(f"  工具调用: {result['stats']['tool_calls']}")
print(f"  总耗时: {result['stats']['execution_time']:.2f}s")
print(f"  Token消耗: {result['stats']['total_tokens']}")
print(f"  成本: ${result['stats']['total_cost']:.4f}")
```

**Agent执行响应示例**：

```json
{
  "task_id": "task-789",
  "status": "completed",
  "plan": [
    {
      "step": 1,
      "description": "搜索2024年Q4人工智能市场报告",
      "tool": "web_search"
    },
    {
      "step": 2,
      "description": "从知识库查询历史市场数据",
      "tool": "knowledge_base"
    },
    {
      "step": 3,
      "description": "计算市场增长率和预测值",
      "tool": "calculator"
    },
    {
      "step": 4,
      "description": "整合数据生成分析报告",
      "tool": "llm_synthesis"
    }
  ],
  "execution_trace": [
    {
      "step": 1,
      "step_type": "tool_call",
      "thought": "需要获取最新的市场数据，使用网络搜索工具",
      "action": "web_search",
      "action_input": "2024 Q4 AI market report size players",
      "tool_result": "根据Gartner报告，2024年Q4全球AI市场规模达到1500亿美元...",
      "observation": "成功获取市场规模数据"
    },
    {
      "step": 2,
      "step_type": "tool_call",
      "thought": "查询知识库中的历史数据以进行对比",
      "action": "knowledge_base",
      "action_input": "人工智能市场 历史数据 2023 Q4",
      "tool_result": "2023年Q4市场规模为1200亿美元，同比增长25%...",
      "observation": "获取历史对比数据"
    },
    {
      "step": 3,
      "step_type": "tool_call",
      "thought": "计算增长率",
      "action": "calculator",
      "action_input": "(1500-1200)/1200*100",
      "tool_result": "25.0",
      "observation": "年增长率为25%"
    },
    {
      "step": 4,
      "step_type": "synthesis",
      "thought": "已收集足够数据，现在整合生成报告",
      "action": "final_answer",
      "action_input": "综合市场数据生成分析报告"
    }
  ],
  "final_result": "## 2024年Q4人工智能市场趋势分析\n\n### 市场规模\n- 全球市场规模：1500亿美元\n- 同比增长：25%\n\n### 主要玩家\n1. OpenAI - GPT系列领先\n2. Google - Gemini生态\n3. Microsoft - Azure AI平台\n4. Amazon - AWS AI服务\n\n### 增长预测\n- 2025年预计达到1875亿美元\n- 增长驱动因素：企业AI应用、生成式AI普及、边缘AI...",
  "stats": {
    "total_steps": 4,
    "tool_calls": 3,
    "execution_time": 45.2,
    "total_tokens": 8500,
    "total_cost": 0.17
  }
}
```

### 2.3 多模态处理实战

#### 场景：文档OCR + 表格解析

```python
# 上传图片进行OCR
files = {
    'file': open('invoice.jpg', 'rb')
}
data = {
    'mode': 'ocr_table',  # OCR + 表格识别
    'language': 'zh-CN'
}

response = requests.post(
    "http://localhost:8008/api/v1/multimodal/process",
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    files=files,
    data=data
)

result = response.json()

# 提取结构化数据
print("识别文本:")
print(result["text"])

print("\n表格数据:")
for table in result["tables"]:
    print(f"表格 {table['table_id']}:")
    for row in table['rows']:
        print("  ", " | ".join(row))

print("\n置信度:", result["confidence"])
```

---

## 3. 微服务开发最佳实践

### 3.1 Go服务开发规范

#### 项目结构（Clean Architecture）

```
cmd/your-service/
├── main.go                    # 入口文件
├── config.go                  # 配置定义
├── wire.go                    # 依赖注入
├── wire_gen.go                # Wire生成文件
├── internal/
│   ├── biz/                   # 业务逻辑层（Use Cases）
│   │   └── *_usecase.go
│   ├── data/                  # 数据访问层（Repository）
│   │   └── *_repo.go
│   ├── domain/                # 领域模型（Entities + Value Objects）
│   │   └── *.go
│   ├── server/                # 服务器层
│   │   ├── grpc.go
│   │   └── http.go
│   └── service/               # 服务接口层（gRPC实现）
│       └── *_service.go
└── README.md
```

#### 依赖注入最佳实践（Wire）

```go
// wire.go
//go:build wireinject
// +build wireinject

package main

import (
    "voicehelper/cmd/your-service/internal/biz"
    "voicehelper/cmd/your-service/internal/data"
    "voicehelper/cmd/your-service/internal/server"
    "voicehelper/cmd/your-service/internal/service"

    "github.com/go-kratos/kratos/v2"
    "github.com/go-kratos/kratos/v2/log"
    "github.com/google/wire"
)

// wireApp 定义依赖注入关系
func wireApp(cfg *Config, logger log.Logger) (*kratos.App, func(), error) {
    // 声明Provider集合（按依赖层次组织）
    wire.Build(
        // 1. Data层（最底层）
        data.ProviderSet,    // 包含: NewDB, NewRedis, *Repo

        // 2. Business Logic层
        biz.ProviderSet,     // 包含: *Usecase

        // 3. Service层
        service.ProviderSet, // 包含: *Service

        // 4. Server层
        server.ProviderSet,  // 包含: NewGRPCServer, NewHTTPServer

        // 5. App
        newApp,
    )
    return nil, nil, nil
}

// 执行Wire生成：go generate ./...
//go:generate wire
```

```go
// internal/data/data.go - Data层Provider示例
package data

import (
    "github.com/google/wire"
    "gorm.io/driver/postgres"
    "gorm.io/gorm"
)

// ProviderSet 是Data层的Wire Provider集合
var ProviderSet = wire.NewSet(
    NewDB,
    NewRedis,
    NewUserRepo,
    NewTenantRepo,
    NewCache,
)

// NewDB 创建数据库连接
func NewDB(cfg *Config) (*gorm.DB, func(), error) {
    db, err := gorm.Open(postgres.Open(cfg.Data.Database.Source), &gorm.Config{
        Logger: logger.Default.LogMode(logger.Info),
    })
    if err != nil {
        return nil, nil, err
    }

    // 设置连接池
    sqlDB, _ := db.DB()
    sqlDB.SetMaxOpenConns(50)
    sqlDB.SetMaxIdleConns(10)
    sqlDB.SetConnMaxLifetime(time.Hour)

    // 返回清理函数
    cleanup := func() {
        sqlDB.Close()
    }

    return db, cleanup, nil
}
```

#### 错误处理规范

```go
// pkg/errors/errors.go - 统一错误定义
package errors

import (
    "fmt"
    "net/http"
)

// AppError 应用错误
type AppError struct {
    Code       string                 `json:"code"`        // 错误码
    Message    string                 `json:"message"`     // 用户可见消息
    HTTPStatus int                    `json:"-"`           // HTTP状态码
    Details    map[string]interface{} `json:"details,omitempty"` // 详细信息
}

func (e *AppError) Error() string {
    return fmt.Sprintf("[%s] %s", e.Code, e.Message)
}

// 预定义错误构造函数
func NewUnauthorized(code, message string) *AppError {
    return &AppError{
        Code:       code,
        Message:    message,
        HTTPStatus: http.StatusUnauthorized,
    }
}

func NewNotFound(code, message string) *AppError {
    return &AppError{
        Code:       code,
        Message:    message,
        HTTPStatus: http.StatusNotFound,
    }
}

func NewInternalServerError(code, message string) *AppError {
    return &AppError{
        Code:       code,
        Message:    message,
        HTTPStatus: http.StatusInternalServerError,
    }
}

// 使用示例
func (uc *UserUsecase) GetUser(ctx context.Context, id string) (*domain.User, error) {
    user, err := uc.repo.GetByID(ctx, id)
    if err != nil {
        if errors.Is(err, gorm.ErrRecordNotFound) {
            return nil, pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
        }
        return nil, pkgErrors.NewInternalServerError("DB_ERROR", "数据库错误")
    }
    return user, nil
}
```

#### 并发控制最佳实践

```go
// 使用errgroup进行并发控制
import (
    "golang.org/x/sync/errgroup"
)

func (s *Service) ProcessBatch(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(10) // 限制并发数

    for _, item := range items {
        item := item // 闭包变量
        g.Go(func() error {
            return s.ProcessItem(ctx, item)
        })
    }

    return g.Wait() // 等待所有goroutine完成
}

// 使用sync.Map处理并发读写
var cache sync.Map

func (s *Service) GetOrLoad(key string) (interface{}, error) {
    // 尝试从缓存读取
    if val, ok := cache.Load(key); ok {
        return val, nil
    }

    // 缓存未命中，加载数据
    val, err := s.repo.Get(key)
    if err != nil {
        return nil, err
    }

    // 存入缓存
    cache.Store(key, val)
    return val, nil
}
```

### 3.2 Python服务开发规范

#### FastAPI最佳实践

```python
# main.py - 应用入口
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动阶段
    print("Starting application...")

    # 初始化资源
    app.state.db_pool = await init_db_pool()
    app.state.redis_client = await init_redis()
    app.state.llm_client = init_llm_client()

    yield

    # 关闭阶段
    print("Shutting down...")
    await app.state.db_pool.close()
    await app.state.redis_client.close()

app = FastAPI(
    title="Your Service",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.routers import items, users
app.include_router(items.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
```

#### 异步数据库访问

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/dbname"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # 开发环境显示SQL
    pool_size=20,  # 连接池大小
    max_overflow=0,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

# app/routers/items.py - 使用依赖注入
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

router = APIRouter()

@router.get("/items/{item_id}")
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Item).where(Item.id == item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item
```

#### Pydantic数据验证

```python
# app/models/schemas.py
from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    username: str = Field(..., min_length=3, max_length=32)

    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('密码必须包含大写字母')
        if not any(c.islower() for c in v):
            raise ValueError('密码必须包含小写字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含数字')
        return v

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime

    class Config:
        from_attributes = True  # 支持ORM模型

class PaginatedResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
```

---

## 4. AI服务集成案例

### 4.1 多模型路由与成本优化

#### 场景：根据查询复杂度智能选择模型

```python
# app/routing/model_selector.py
from typing import Dict, Any

class IntelligentModelSelector:
    """智能模型选择器"""

    def __init__(self):
        self.models = {
            "gpt-4": {
                "cost_per_1k_tokens": 0.03,
                "quality_score": 0.95,
                "latency_ms": 2000,
                "context_window": 128000,
            },
            "gpt-3.5-turbo": {
                "cost_per_1k_tokens": 0.002,
                "quality_score": 0.80,
                "latency_ms": 800,
                "context_window": 16384,
            },
            "qwen-turbo": {
                "cost_per_1k_tokens": 0.001,
                "quality_score": 0.75,
                "latency_ms": 600,
                "context_window": 8192,
            },
        }

    def select_model(
        self,
        query: str,
        context_length: int,
        priority: str = "balanced"  # cost/quality/latency/balanced
    ) -> str:
        """
        根据查询特征选择最优模型

        Args:
            query: 用户查询
            context_length: 上下文长度（tokens）
            priority: 优先级策略

        Returns:
            model_name: 选择的模型名称
        """
        # 1. 分析查询复杂度
        complexity = self._analyze_complexity(query)

        # 2. 过滤上下文窗口不足的模型
        available_models = {
            name: config
            for name, config in self.models.items()
            if config["context_window"] >= context_length
        }

        # 3. 根据策略选择模型
        if priority == "cost":
            return min(available_models, key=lambda x: available_models[x]["cost_per_1k_tokens"])

        elif priority == "quality":
            if complexity == "high":
                return "gpt-4"
            elif complexity == "medium":
                return "gpt-3.5-turbo"
            else:
                return "qwen-turbo"

        elif priority == "latency":
            return min(available_models, key=lambda x: available_models[x]["latency_ms"])

        else:  # balanced
            # 综合评分 = 质量权重 * 质量分 - 成本权重 * 成本 - 延迟权重 * 延迟
            scores = {}
            for name, config in available_models.items():
                score = (
                    0.5 * config["quality_score"]
                    - 0.3 * config["cost_per_1k_tokens"] * 10
                    - 0.2 * config["latency_ms"] / 1000
                )
                scores[name] = score

            return max(scores, key=scores.get)

    def _analyze_complexity(self, query: str) -> str:
        """分析查询复杂度"""
        query_lower = query.lower()

        # 高复杂度关键词
        high_complexity_keywords = [
            "分析", "对比", "评估", "预测", "推理", "解释",
            "多步骤", "复杂", "深入"
        ]

        # 低复杂度关键词
        low_complexity_keywords = [
            "是什么", "定义", "简单", "快速", "列出"
        ]

        if any(kw in query_lower for kw in high_complexity_keywords):
            return "high"
        elif any(kw in query_lower for kw in low_complexity_keywords):
            return "low"
        else:
            return "medium"

# 使用示例
selector = IntelligentModelSelector()

# 简单查询 → 使用便宜模型
model = selector.select_model(
    query="什么是Python？",
    context_length=1000,
    priority="cost"
)
print(model)  # qwen-turbo

# 复杂分析 → 使用高质量模型
model = selector.select_model(
    query="分析并对比React和Vue的架构设计优劣",
    context_length=5000,
    priority="quality"
)
print(model)  # gpt-4
```

### 4.2 LLM调用重试与降级策略

```python
# app/infrastructure/llm_client.py
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from openai import AsyncOpenAI, RateLimitError, APIError

class ResilientLLMClient:
    """具备重试和降级的LLM客户端"""

    def __init__(self):
        self.primary_client = AsyncOpenAI(api_key="primary_key")
        self.fallback_client = AsyncOpenAI(
            api_key="fallback_key",
            base_url="https://api.fallback-provider.com/v1"
        )
        self.local_cache = {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError))
    )
    async def complete(
        self,
        messages: list,
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        use_cache: bool = True
    ) -> dict:
        """
        LLM补全（带重试和降级）

        Args:
            messages: 消息列表
            model: 模型名称
            max_tokens: 最大token数
            temperature: 温度参数
            use_cache: 是否使用缓存

        Returns:
            response: LLM响应
        """
        # 1. 检查缓存
        if use_cache:
            cache_key = self._make_cache_key(messages, model)
            if cache_key in self.local_cache:
                return self.local_cache[cache_key]

        try:
            # 2. 主LLM调用
            response = await self._call_primary(
                messages, model, max_tokens, temperature
            )

            # 3. 缓存结果
            if use_cache:
                self.local_cache[cache_key] = response

            return response

        except RateLimitError:
            # 4. 限流错误 → 等待后重试（由tenacity自动处理）
            raise

        except APIError as e:
            # 5. API错误 → 降级到备用模型
            print(f"Primary LLM failed: {e}, falling back to secondary")
            return await self._call_fallback(
                messages, model, max_tokens, temperature
            )

        except Exception as e:
            # 6. 其他错误 → 返回预设响应
            print(f"LLM call failed completely: {e}")
            return self._get_default_response()

    async def _call_primary(self, messages, model, max_tokens, temperature):
        """调用主LLM"""
        response = await self.primary_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return {
            "content": response.choices[0].message.content,
            "model": model,
            "tokens": response.usage.total_tokens,
            "provider": "primary"
        }

    async def _call_fallback(self, messages, model, max_tokens, temperature):
        """调用备用LLM"""
        # 降级到更便宜的模型
        fallback_model = "gpt-3.5-turbo" if model == "gpt-4" else model

        response = await self.fallback_client.chat.completions.create(
            model=fallback_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return {
            "content": response.choices[0].message.content,
            "model": fallback_model,
            "tokens": response.usage.total_tokens,
            "provider": "fallback"
        }

    def _get_default_response(self):
        """返回默认响应（最后降级）"""
        return {
            "content": "抱歉，服务暂时不可用，请稍后重试。",
            "model": "fallback",
            "tokens": 0,
            "provider": "default"
        }

    def _make_cache_key(self, messages, model):
        """生成缓存键"""
        import hashlib
        import json

        key_data = json.dumps({"messages": messages, "model": model}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

# 使用示例
client = ResilientLLMClient()

messages = [
    {"role": "system", "content": "你是一个专业的助手"},
    {"role": "user", "content": "什么是机器学习？"}
]

# 自动重试 + 降级
response = await client.complete(messages, model="gpt-4")
print(response["content"])
print(f"使用模型: {response['model']}, 提供商: {response['provider']}")
```

---

## 5. 性能优化实战

### 5.1 数据库查询优化

#### 问题：N+1查询导致性能瓶颈

**反面示例（N+1查询）**：

```go
// ❌ 错误示例：N+1查询
func (r *UserRepository) GetUsersWithPosts(ctx context.Context) ([]*domain.User, error) {
    // 1. 查询所有用户（1次查询）
    users, err := r.db.WithContext(ctx).Find(&users).Error
    if err != nil {
        return nil, err
    }

    // 2. 循环查询每个用户的帖子（N次查询）
    for i, user := range users {
        var posts []domain.Post
        r.db.WithContext(ctx).Where("user_id = ?", user.ID).Find(&posts)
        users[i].Posts = posts  // N次查询
    }

    return users, nil
}
// 总查询次数：1 + N = O(N)
```

**正确示例（JOIN或Preload）**：

```go
// ✅ 正确示例：使用Preload（2次查询）
func (r *UserRepository) GetUsersWithPosts(ctx context.Context) ([]*domain.User, error) {
    var users []*domain.User

    err := r.db.WithContext(ctx).
        Preload("Posts").  // GORM自动处理关联查询
        Find(&users).Error

    return users, err
}
// 总查询次数：2（1次users + 1次posts）

// ✅ 或者使用手动JOIN
func (r *UserRepository) GetUsersWithPostsJoin(ctx context.Context) ([]*domain.User, error) {
    var results []struct {
        User domain.User
        Post domain.Post
    }

    err := r.db.WithContext(ctx).
        Table("users").
        Select("users.*, posts.*").
        Joins("LEFT JOIN posts ON posts.user_id = users.id").
        Scan(&results).Error

    // 聚合结果
    userMap := make(map[string]*domain.User)
    for _, r := range results {
        if _, exists := userMap[r.User.ID]; !exists {
            userMap[r.User.ID] = &r.User
        }
        userMap[r.User.ID].Posts = append(userMap[r.User.ID].Posts, r.Post)
    }

    // 转换为切片
    users := make([]*domain.User, 0, len(userMap))
    for _, user := range userMap {
        users = append(users, user)
    }

    return users, err
}
// 总查询次数：1（单次JOIN）
```

#### 索引优化

```sql
-- 1. 查看慢查询日志
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 1000  -- 超过1秒
ORDER BY mean_exec_time DESC
LIMIT 20;

-- 2. 分析查询计划
EXPLAIN ANALYZE
SELECT * FROM users
WHERE email = 'user@example.com';

-- 3. 创建索引
-- 单列索引
CREATE INDEX idx_users_email ON users(email);

-- 复合索引（顺序很重要）
CREATE INDEX idx_users_tenant_status ON users(tenant_id, status);

-- 部分索引（仅索引活跃用户）
CREATE INDEX idx_active_users_email ON users(email)
WHERE status = 'active';

-- 表达式索引
CREATE INDEX idx_users_lower_email ON users(LOWER(email));

-- 4. 验证索引使用
EXPLAIN ANALYZE
SELECT * FROM users
WHERE email = 'user@example.com';
-- 应看到：Index Scan using idx_users_email
```

### 5.2 缓存策略优化

#### 多级缓存架构

```python
# app/cache/multi_level_cache.py
import asyncio
from typing import Any, Optional
from functools import wraps

class MultiLevelCache:
    """多级缓存：本地内存 → Redis → 数据库"""

    def __init__(self, redis_client, db_client):
        self.local_cache = {}  # 本地LRU缓存
        self.redis_client = redis_client
        self.db_client = db_client

        # LRU配置
        self.local_max_size = 1000
        self.access_order = []

    async def get(
        self,
        key: str,
        fetch_func: callable,
        ttl: int = 3600,
        use_local: bool = True
    ) -> Any:
        """
        多级缓存获取

        Args:
            key: 缓存键
            fetch_func: 数据获取函数（缓存未命中时调用）
            ttl: Redis TTL（秒）
            use_local: 是否使用本地缓存

        Returns:
            data: 缓存数据
        """
        # L1：本地缓存
        if use_local and key in self.local_cache:
            self._update_access(key)
            return self.local_cache[key]

        # L2：Redis缓存
        redis_value = await self.redis_client.get(key)
        if redis_value:
            data = self._deserialize(redis_value)

            # 回填本地缓存
            if use_local:
                self._set_local(key, data)

            return data

        # L3：数据库（缓存未命中）
        data = await fetch_func()

        # 回填所有缓存层
        await self.redis_client.setex(key, ttl, self._serialize(data))
        if use_local:
            self._set_local(key, data)

        return data

    def _set_local(self, key: str, value: Any):
        """设置本地缓存（LRU淘汰）"""
        if len(self.local_cache) >= self.local_max_size:
            # 淘汰最少使用的key
            lru_key = self.access_order.pop(0)
            del self.local_cache[lru_key]

        self.local_cache[key] = value
        self.access_order.append(key)

    def _update_access(self, key: str):
        """更新访问顺序"""
        self.access_order.remove(key)
        self.access_order.append(key)

    def _serialize(self, data: Any) -> str:
        """序列化"""
        import json
        return json.dumps(data)

    def _deserialize(self, data: str) -> Any:
        """反序列化"""
        import json
        return json.loads(data)

# 使用装饰器简化缓存使用
def cached(key_pattern: str, ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 构建缓存键
            cache = get_cache_instance()
            key = key_pattern.format(*args, **kwargs)

            # 定义数据获取函数
            async def fetch_func():
                return await func(*args, **kwargs)

            # 从缓存获取或执行函数
            return await cache.get(key, fetch_func, ttl)

        return wrapper
    return decorator

# 应用示例
@cached(key_pattern="user:{user_id}", ttl=3600)
async def get_user(user_id: str):
    # 此函数仅在缓存未命中时执行
    async with db.session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

# 调用（自动缓存）
user = await get_user("user-123")
```

### 5.3 批量操作优化

#### 批量插入优化

```python
# 反面示例：逐条插入
async def insert_users_slow(users: list[User]):
    async with db.session() as session:
        for user in users:
            session.add(user)  # N次INSERT
            await session.commit()
    # 耗时：N * 单次INSERT时间

# 正确示例：批量插入
async def insert_users_fast(users: list[User]):
    async with db.session() as session:
        session.add_all(users)  # 1次批量INSERT
        await session.commit()
    # 耗时：1次INSERT时间

# PostgreSQL原生批量插入（更快）
async def insert_users_bulk(users: list[dict]):
    async with db.engine.begin() as conn:
        await conn.execute(
            insert(User),
            users  # 批量参数
        )
    # 使用COPY命令（最快）
    import pandas as pd
    from io import StringIO

    # 转换为CSV
    df = pd.DataFrame(users)
    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    # COPY命令插入
    async with db.engine.raw_connection() as conn:
        cursor = conn.cursor()
        cursor.copy_from(buffer, 'users', sep=',', columns=df.columns)
        await conn.commit()
```

---

## 6. 故障处理与监控

### 6.1 全链路追踪实战

#### OpenTelemetry集成

```python
# app/telemetry/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def init_tracing(service_name: str, otlp_endpoint: str):
    """初始化追踪"""
    # 1. 创建TracerProvider
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": "production"
        })
    )

    # 2. 配置导出器（发送到Jaeger/Tempo）
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)

    # 3. 设置全局TracerProvider
    trace.set_tracer_provider(provider)

    return trace.get_tracer(__name__)

# 在main.py中初始化
tracer = init_tracing(
    service_name="rag-engine",
    otlp_endpoint="http://jaeger:4317"
)

# 自动instrumentation
FastAPIInstrumentor.instrument_app(app)  # 自动追踪HTTP请求
SQLAlchemyInstrumentor().instrument()    # 自动追踪数据库查询
RedisInstrumentor().instrument()          # 自动追踪Redis操作

# 手动创建Span
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_document(doc_id: str):
    # 创建父Span
    with tracer.start_as_current_span("process_document") as span:
        span.set_attribute("document.id", doc_id)

        # 子Span：解析文档
        with tracer.start_as_current_span("parse_document"):
            content = await parse_pdf(doc_id)
            span.set_attribute("document.pages", len(content))

        # 子Span：向量化
        with tracer.start_as_current_span("vectorize"):
            vectors = await embed_text(content)
            span.set_attribute("vectors.count", len(vectors))

        # 子Span：存储
        with tracer.start_as_current_span("store_vectors"):
            await milvus_client.insert(vectors)

        span.set_status(Status(StatusCode.OK))
        return {"status": "success"}
```

#### 追踪可视化（Jaeger UI）

```bash
# 访问 Jaeger UI
open http://localhost:16686

# 搜索Trace
# 1. 选择Service: rag-engine
# 2. 选择Operation: POST /api/v1/rag/query
# 3. 设置时间范围：Last 1 hour
# 4. 点击"Find Traces"

# Trace详情展示：
# - 总耗时：2.5s
# - Span层级：
#   ├─ POST /api/v1/rag/query (2.5s)
#   │  ├─ query_classifier (0.1s)
#   │  ├─ hybrid_retrieval (0.8s)
#   │  │  ├─ vector_search (0.5s)
#   │  │  └─ bm25_search (0.3s)
#   │  ├─ reranking (0.4s)
#   │  └─ llm_generation (1.2s)
```

### 6.2 告警配置

#### Prometheus告警规则

```yaml
# prometheus/alerts/voicehelper.yml
groups:
  - name: voicehelper_alerts
    interval: 30s
    rules:
      # 1. 服务可用性告警
      - alert: ServiceDown
        expr: up{job=~".*-service"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "服务不可用: {{ $labels.job }}"
          description: "{{ $labels.instance }} 已宕机超过2分钟"

      # 2. 高错误率告警
      - alert: HighErrorRate
        expr: |
          (
            rate(http_requests_total{status=~"5.."}[5m])
            / rate(http_requests_total[5m])
          ) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "错误率过高: {{ $labels.service }}"
          description: "{{ $labels.service }} 错误率超过5%（当前：{{ $value | humanizePercentage }}）"

      # 3. 延迟告警
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 3.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95延迟过高: {{ $labels.service }}"
          description: "{{ $labels.service }} P95延迟：{{ $value }}s"

      # 4. RAG缓存命中率低
      - alert: LowCacheHitRate
        expr: rag_cache_hit_ratio < 0.3
        for: 15m
        labels:
          severity: info
        annotations:
          summary: "RAG缓存命中率过低"
          description: "缓存命中率仅{{ $value | humanizePercentage }}，建议检查缓存配置"

      # 5. LLM成本超预算
      - alert: BudgetExceeded
        expr: |
          sum by (tenant_id) (llm_cost_usd_total)
          > on(tenant_id) tenant_budget_limit_usd
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "租户预算超限: {{ $labels.tenant_id }}"
          description: "本月成本：${{ $value }}，已超预算"

      # 6. 数据库连接池耗尽
      - alert: DatabasePoolExhausted
        expr: |
          (
            database_connections_active
            / database_connections_max
          ) > 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "数据库连接池即将耗尽"
          description: "{{ $labels.instance }} 连接池使用率：{{ $value | humanizePercentage }}"
```

#### AlertManager配置

```yaml
# alertmanager/config.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'

  routes:
    # 关键告警立即通知
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true

    # 警告级别告警发送到Slack
    - match:
        severity: warning
      receiver: 'slack'

    # 信息级别仅记录
    - match:
        severity: info
      receiver: 'log'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://webhook-receiver:8080/alerts'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'your-pagerduty-key'
        description: '{{ .CommonAnnotations.summary }}'

  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#voicehelper-alerts'
        title: '[{{ .Status | toUpper }}] {{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'

  - name: 'log'
    webhook_configs:
      - url: 'http://log-receiver:8080/alerts'
```

---

## 7. 生产部署经验

### 7.1 Kubernetes部署最佳实践

#### 资源配置

```yaml
# deployments/k8s/services/rag-engine.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-engine
  namespace: voiceassistant-prod
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # 滚动更新时最多新增1个Pod
      maxUnavailable: 0  # 滚动更新时不允许Pod不可用

  selector:
    matchLabels:
      app: rag-engine

  template:
    metadata:
      labels:
        app: rag-engine
        version: v2.0.0
      annotations:
        sidecar.istio.io/inject: "true"
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"

    spec:
      # 1. 反亲和性（分散到不同节点）
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - rag-engine
              topologyKey: kubernetes.io/hostname

      # 2. 初始化容器（等待依赖服务就绪）
      initContainers:
      - name: wait-for-redis
        image: busybox:1.35
        command: ['sh', '-c', 'until nc -z redis 6379; do sleep 2; done']

      containers:
      - name: rag-engine
        image: voicehelper/rag-engine:v2.0.0
        imagePullPolicy: IfNotPresent

        ports:
        - containerPort: 8006
          name: http
          protocol: TCP
        - containerPort: 9090
          name: metrics
          protocol: TCP

        # 3. 资源请求与限制
        resources:
          requests:
            cpu: "1000m"      # 1核（保证）
            memory: "2Gi"     # 2GB（保证）
          limits:
            cpu: "4000m"      # 最多4核
            memory: "8Gi"     # 最多8GB

        # 4. 环境变量（从ConfigMap和Secret注入）
        env:
        - name: CONFIG_MODE
          value: "nacos"
        - name: NACOS_SERVER_ADDR
          valueFrom:
            configMapKeyRef:
              name: voicehelper-config
              key: nacos.server.addr
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: openai-api-key
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: password

        # 5. 健康检查
        livenessProbe:
          httpGet:
            path: /health
            port: 8006
          initialDelaySeconds: 60   # 启动后60秒开始检查
          periodSeconds: 10         # 每10秒检查一次
          timeoutSeconds: 5         # 超时5秒视为失败
          failureThreshold: 3       # 连续3次失败重启Pod

        readinessProbe:
          httpGet:
            path: /ready
            port: 8006
          initialDelaySeconds: 30   # 启动后30秒开始检查
          periodSeconds: 5          # 每5秒检查一次
          timeoutSeconds: 3
          failureThreshold: 2       # 连续2次失败标记为未就绪

        # 6. 生命周期钩子
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]  # 优雅关闭（等待连接排空）

        # 7. 挂载配置
        volumeMounts:
        - name: config
          mountPath: /app/configs
          readOnly: true

      volumes:
      - name: config
        configMap:
          name: rag-engine-config

---
# HPA（水平自动扩缩容）
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-engine-hpa
  namespace: voiceassistant-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-engine

  minReplicas: 3
  maxReplicas: 20

  metrics:
  # 基于CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70

  # 基于内存
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

  # 基于自定义指标（RPS）
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"

  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60   # 扩容稳定窗口1分钟
      policies:
      - type: Percent
        value: 50       # 每次最多扩容50%
        periodSeconds: 60
      - type: Pods
        value: 2        # 或每次最多增加2个Pod
        periodSeconds: 60

    scaleDown:
      stabilizationWindowSeconds: 300  # 缩容稳定窗口5分钟
      policies:
      - type: Percent
        value: 10       # 每次最多缩容10%
        periodSeconds: 60
```

#### PodDisruptionBudget（防止意外中断）

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: rag-engine-pdb
  namespace: voiceassistant-prod
spec:
  minAvailable: 2  # 至少保持2个Pod可用
  selector:
    matchLabels:
      app: rag-engine
```

### 7.2 CI/CD最佳实践

#### GitHub Actions工作流

```yaml
# .github/workflows/deploy.yml
name: Build and Deploy

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/rag-engine

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r algo/rag-engine/requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: |
          cd algo/rag-engine
          pytest tests/ --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=semver,pattern={{version}}

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: ./algo/rag-engine
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up kubectl
        uses: azure/setup-kubectl@v3
        with:
          version: 'latest'

      - name: Configure kubeconfig
        run: |
          echo "${{ secrets.KUBECONFIG }}" > kubeconfig.yaml
          export KUBECONFIG=kubeconfig.yaml

      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/rag-engine \
            rag-engine=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -n voiceassistant-prod

          kubectl rollout status deployment/rag-engine -n voiceassistant-prod

      - name: Verify deployment
        run: |
          kubectl get pods -n voiceassistant-prod -l app=rag-engine
```

---

## 8. 常见问题与解决方案

### 8.1 内存泄漏排查

#### 问题：Python服务内存持续增长

**排查步骤**：

```bash
# 1. 使用memory_profiler监控
pip install memory_profiler

# 在代码中添加装饰器
from memory_profiler import profile

@profile
async def process_large_document(doc_id: str):
    # 函数逻辑
    pass

# 运行服务并查看内存使用
python -m memory_profiler main.py

# 2. 使用tracemalloc追踪内存分配
import tracemalloc

# 启动追踪
tracemalloc.start()

# 执行一些操作
# ...

# 获取统计信息
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 ]")
for stat in top_stats[:10]:
    print(stat)

# 3. 使用objgraph查找引用循环
pip install objgraph

import objgraph
objgraph.show_most_common_types(limit=20)
objgraph.show_growth()
```

**常见原因与解决方案**：

1. **未关闭的数据库连接**
```python
# ❌ 错误：未关闭连接
async def query_data():
    session = SessionLocal()
    result = await session.execute(query)
    return result  # 连接未关闭

# ✅ 正确：使用上下文管理器
async def query_data():
    async with SessionLocal() as session:
        result = await session.execute(query)
        return result
```

2. **全局缓存无限增长**
```python
# ❌ 错误：无限缓存
cache = {}

def get_data(key):
    if key not in cache:
        cache[key] = expensive_operation(key)
    return cache[key]

# ✅ 正确：使用LRU缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_data(key):
    return expensive_operation(key)
```

3. **循环引用**
```python
# ❌ 错误：循环引用
class Node:
    def __init__(self):
        self.children = []
        self.parent = None

    def add_child(self, child):
        self.children.append(child)
        child.parent = self  # 循环引用

# ✅ 正确：使用弱引用
import weakref

class Node:
    def __init__(self):
        self.children = []
        self._parent = None

    @property
    def parent(self):
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, value):
        self._parent = weakref.ref(value) if value else None
```

### 8.2 gRPC连接超时

#### 问题：gRPC客户端频繁超时

**解决方案**：

```go
// 1. 增加超时时间
conn, err := grpc.Dial(
    "service:9000",
    grpc.WithTimeout(60*time.Second),  // 连接超时
    grpc.WithBlock(),  // 阻塞直到连接建立
)

// 2. 配置重试策略
retryPolicy := `{
    "methodConfig": [{
        "name": [{"service": "identity.IdentityService"}],
        "waitForReady": true,
        "retryPolicy": {
            "MaxAttempts": 4,
            "InitialBackoff": ".1s",
            "MaxBackoff": "1s",
            "BackoffMultiplier": 2,
            "RetryableStatusCodes": ["UNAVAILABLE"]
        }
    }]
}`

conn, err := grpc.Dial(
    "service:9000",
    grpc.WithDefaultServiceConfig(retryPolicy),
)

// 3. 使用Context设置请求级超时
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

response, err := client.GetUser(ctx, &pb.GetUserRequest{Id: "123"})
if err != nil {
    if errors.Is(err, context.DeadlineExceeded) {
        // 处理超时
    }
}

// 4. 配置KeepAlive（防止空闲连接被关闭）
conn, err := grpc.Dial(
    "service:9000",
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Time:                10 * time.Second, // 每10秒发送ping
        Timeout:             3 * time.Second,  // ping超时3秒
        PermitWithoutStream: true,
    }),
)
```

### 8.3 向量检索召回率低

#### 问题：RAG系统检索不到相关文档

**排查与优化**：

```python
# 1. 检查Embedding质量
async def analyze_embedding_quality(texts: list[str]):
    """分析Embedding质量"""
    embeddings = await get_embeddings(texts)

    # 计算相似度矩阵
    from sklearn.metrics.pairwise import cosine_similarity
    similarity_matrix = cosine_similarity(embeddings)

    # 应该看到语义相关的文本相似度高
    print("相似度矩阵:")
    print(similarity_matrix)

    # 检查向量分布
    import numpy as np
    print("\n向量统计:")
    print(f"均值: {np.mean(embeddings, axis=0)[:5]}")  # 前5维
    print(f"标准差: {np.std(embeddings, axis=0)[:5]}")
    print(f"范数: {[np.linalg.norm(e) for e in embeddings]}")

# 2. 调整分块策略
# ❌ 错误：分块过大导致语义混杂
def chunk_by_tokens(text, max_tokens=1000):
    # 简单按token数切分
    tokens = tokenizer.encode(text)
    chunks = [tokens[i:i+max_tokens] for i in range(0, len(tokens), max_tokens)]
    return [tokenizer.decode(chunk) for chunk in chunks]

# ✅ 正确：语义分块（保持段落完整）
def semantic_chunking(text, max_tokens=500, overlap=50):
    """语义分块（保持段落完整性）"""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if current_tokens + para_tokens > max_tokens:
            # 当前chunk已满，保存并开始新chunk
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))

                # 保留overlap用于下一个chunk（上下文连续性）
                overlap_paras = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk
                current_chunk = overlap_paras
                current_tokens = sum(count_tokens(p) for p in overlap_paras)

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks

# 3. 优化检索参数
async def optimized_retrieval(query: str, top_k: int = 20):
    """优化的混合检索"""
    # 步骤1：扩大初始召回（Top-K增大）
    vector_results = await vector_search(query, top_k=top_k * 2)  # Top-40
    bm25_results = await bm25_search(query, top_k=top_k * 2)

    # 步骤2：RRF融合
    fused = reciprocal_rank_fusion([vector_results, bm25_results])

    # 步骤3：Cross-Encoder重排（精排Top-K）
    reranked = await rerank(query, fused[:top_k * 2], top_k=top_k)

    return reranked

# 4. 查询扩展（Query Expansion）
async def expand_query(query: str) -> list[str]:
    """查询扩展（生成同义查询）"""
    prompt = f"""
    原始查询：{query}

    请生成3个语义相同但表达不同的查询，用于扩大检索范围：
    1.
    2.
    3.
    """

    response = await llm_client.complete(prompt)
    expanded_queries = parse_numbered_list(response)

    # 使用多个查询并合并结果
    all_results = []
    for q in [query] + expanded_queries:
        results = await vector_search(q, top_k=10)
        all_results.extend(results)

    # 去重并排序
    unique_results = deduplicate_by_id(all_results)
    return sorted(unique_results, key=lambda x: x.score, reverse=True)[:20]
```

---

## 总结

本文档提供了 VoiceHelper 平台的完整实战指南，涵盖：

1. **快速开始**：从零搭建开发环境、首次API调用
2. **核心功能**：RAG完整流程、Agent任务执行、多模态处理
3. **开发最佳实践**：Go/Python服务开发规范、错误处理、并发控制
4. **AI集成**：模型路由、重试降级、成本优化
5. **性能优化**：数据库查询、缓存策略、批量操作
6. **故障处理**：全链路追踪、告警配置、问题排查
7. **生产部署**：Kubernetes配置、CI/CD流程
8. **常见问题**：内存泄漏、gRPC超时、召回率低等

**关键要点**：
- 使用多级缓存提升性能（本地 → Redis → 数据库）
- 数据库避免N+1查询，合理使用索引
- LLM调用必须配置重试和降级策略
- 生产部署使用HPA自动扩缩容
- 全链路追踪（OpenTelemetry）助力问题定位
- Prometheus + Grafana + AlertManager完整监控体系

**下一步学习**：
- 查阅各模块详细文档（VoiceHelper-01-xx.md）
- 阅读API协议指南（api/API-PROTOCOL-GUIDE.md）
- 参考配置管理指南（configs/CONFIG_GUIDE.md）
- 加入Slack频道：#voicehelper-dev
