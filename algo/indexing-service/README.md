# Indexing Service - 文档索引与向量化服务

## 概述

Indexing Service 是 VoiceAssistant 平台的文档索引与向量化服务，负责：

- **文档解析**：支持 PDF、DOCX、TXT、MD、HTML 等多种格式
- **文本分块**：智能文本切分，支持重叠窗口
- **向量化**：使用 BGE-M3 或 OpenAI Embeddings
- **向量存储**：集成 Milvus 向量数据库
- **知识图谱**：构建文档关系图（Neo4j）
- **对象存储**：MinIO 文件存储

## 技术栈

- **FastAPI**: Python Web 框架
- **BGE-M3**: 中文优化的 Embedding 模型
- **Milvus**: 向量数据库
- **Neo4j**: 图数据库
- **MinIO**: S3 兼容对象存储
- **PyPDF2/python-docx**: 文档解析

## 目录结构

```
indexing-service/
├── main.py                 # FastAPI应用入口
├── app/
│   ├── core/              # 核心配置
│   │   ├── config.py      # 配置管理
│   │   └── logging_config.py  # 日志配置
│   ├── models/            # 数据模型
│   │   └── document.py    # 文档相关模型
│   ├── routers/           # API路由
│   │   ├── health.py      # 健康检查
│   │   ├── document.py    # 文档处理
│   │   └── chunk.py       # 文本块管理
│   └── services/          # 业务逻辑
│       ├── document_service.py   # 文档处理服务
│       ├── chunk_service.py      # 分块服务
│       ├── embedding_service.py  # 向量化服务
│       ├── parser_service.py     # 文档解析服务
│       ├── storage_service.py    # 对象存储服务
│       └── vector_service.py     # 向量数据库服务
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker镜像
├── Makefile              # 构建脚本
└── README.md             # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并配置：

```bash
cp .env.example .env
```

### 3. 启动服务

```bash
# 开发模式
make run

# 或直接使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8004
```

### 4. 访问 API 文档

打开浏览器访问：

- Swagger UI: http://localhost:8004/docs
- ReDoc: http://localhost:8004/redoc

## API 端点

### 健康检查

```bash
GET /health
```

### 上传文档

```bash
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: <document_file>
tenant_id: tenant_123
knowledge_base_id: kb_456
```

### 索引文档

```bash
POST /api/v1/documents/index
Content-Type: application/json

{
  "document_id": "doc_abc123",
  "tenant_id": "tenant_123",
  "knowledge_base_id": "kb_456",
  "options": {
    "chunk_size": 512,
    "overlap": 50,
    "build_graph": true
  }
}
```

### 查询索引状态

```bash
GET /api/v1/documents/index/{job_id}
```

### 获取文档块

```bash
GET /api/v1/chunks/{document_id}?offset=0&limit=20
```

### 删除文档

```bash
DELETE /api/v1/documents/{document_id}
```

## 索引流程

```
1. 上传文档 → MinIO
2. 解析文档内容（PDF/DOCX/TXT等）
3. 文本分块（Chunking）
   ├─ 固定大小切分
   ├─ 重叠窗口
   └─ 保留上下文
4. 向量化（Embedding）
   ├─ BGE-M3模型
   └─ 批量处理
5. 存储向量 → Milvus
6. 构建知识图谱 → Neo4j（可选）
7. 完成索引
```

## 文档格式支持

| 格式     | 扩展名  | 解析器        | 状态 |
| -------- | ------- | ------------- | ---- |
| PDF      | `.pdf`  | PyPDF2        | ✅   |
| Word     | `.docx` | python-docx   | ✅   |
| 文本     | `.txt`  | Built-in      | ✅   |
| Markdown | `.md`   | Built-in      | ✅   |
| HTML     | `.html` | BeautifulSoup | ✅   |
| JSON     | `.json` | Built-in      | 🔄   |

## 向量化配置

### BGE-M3 模型

```yaml
EMBEDDING_MODEL: BAAI/bge-m3
EMBEDDING_DIMENSION: 1024
EMBEDDING_BATCH_SIZE: 32
```

### OpenAI Embeddings

```yaml
OPENAI_API_KEY: your-api-key
EMBEDDING_MODEL: text-embedding-3-small
EMBEDDING_DIMENSION: 1536
```

## 分块策略

### 固定大小分块

```python
chunk_size = 512  # 字符数
overlap = 50      # 重叠字符数
```

### 智能分块（高级）

- 按段落边界切分
- 保留完整句子
- 动态调整块大小

## Milvus 集成

### Collection Schema

```python
{
  "chunk_id": "VARCHAR",
  "document_id": "VARCHAR",
  "content": "VARCHAR",
  "embedding": "FLOAT_VECTOR(1024)",
  "tenant_id": "VARCHAR",
  "created_at": "INT64"
}
```

### 索引配置

```python
index_params = {
  "metric_type": "IP",  # Inner Product
  "index_type": "HNSW",
  "params": {"M": 16, "efConstruction": 256}
}
```

## MinIO 配置

```yaml
MINIO_ENDPOINT: localhost:9000
MINIO_ACCESS_KEY: minioadmin
MINIO_SECRET_KEY: minioadmin
MINIO_BUCKET: documents
MINIO_SECURE: false
```

## 知识图谱（Neo4j）

### 节点类型

- **Document**: 文档节点
- **Chunk**: 文本块节点
- **Entity**: 实体节点（NER 提取）

### 关系类型

- **CONTAINS**: 文档包含块
- **NEXT**: 块的顺序关系
- **REFERENCES**: 块引用实体

## Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
make docker-run
```

## 测试

```bash
# 运行测试
make test

# 代码检查
make lint

# 代码格式化
make format
```

## 监控指标

- 文档处理速度（docs/second）
- 分块数量统计
- 向量化耗时
- Milvus 插入性能
- 存储空间使用

## 性能优化

### 1. 批量处理

- 批量向量化（32 texts/batch）
- 批量插入 Milvus
- 并发处理多个文档

### 2. 缓存策略

- 向量缓存（Redis）
- 文档解析缓存
- Embedding 结果缓存

### 3. 资源限制

- 最大文件大小：100MB
- 最大块数：10,000/document
- 并发任务数：10

## 常见问题

### 1. 中文支持

使用 BGE-M3 模型，对中文友好。

### 2. 大文件处理

分批读取，流式处理。

### 3. 向量维度选择

- BGE-M3: 1024 维（推荐）
- OpenAI: 1536 维
- 自定义模型：根据模型选择

## 许可证

MIT License
