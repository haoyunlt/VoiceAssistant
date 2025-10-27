# Knowledge Graph Service 📊

> **知识图谱服务** - 提供实体提取、关系抽取和图谱存储查询功能

---

## 📋 功能特性

### ✅ 已实现

1. **实体提取 (NER)**

   - SpaCy NER 模型
   - 支持多语言（英文/中文）
   - 后备规则提取

2. **关系提取**

   - 依存句法分析
   - SVO 模式匹配
   - 置信度评分

3. **Neo4j 图数据库**

   - 异步 Neo4j 驱动
   - 节点和关系 CRUD
   - Cypher 查询支持

4. **REST API**
   - 实体和关系提取
   - 图谱查询（实体、路径、邻居）
   - 统计信息

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/knowledge-service
pip install -r requirements.txt

# 下载 SpaCy 模型
python -m spacy download en_core_web_sm  # 英文
# python -m spacy download zh_core_web_sm  # 中文
```

### 2. 启动 Neo4j

使用 Docker:

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

或者使用 docker-compose（如果有配置文件）。

### 3. 配置环境变量

创建 `.env` 文件：

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

SPACY_MODEL=en_core_web_sm
LOG_LEVEL=INFO
```

### 4. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8006` 启动。

---

## 📡 API 端点

### 1. 提取实体和关系

**POST** `/api/v1/kg/extract`

```bash
curl -X POST http://localhost:8006/api/v1/kg/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Apple Inc. was founded by Steve Jobs in Cupertino, California.",
    "source": "wikipedia"
  }'
```

**响应**:

```json
{
  "success": true,
  "entities_extracted": 4,
  "entities_stored": 4,
  "relations_extracted": 2,
  "relations_stored": 2
}
```

### 2. 查询实体

**POST** `/api/v1/kg/query/entity`

```bash
curl -X POST http://localhost:8006/api/v1/kg/query/entity \
  -H "Content-Type: application/json" \
  -d '{"entity": "Steve Jobs"}'
```

**响应**:

```json
{
  "id": "4:xxx:0",
  "labels": ["PERSON"],
  "properties": {
    "text": "Steve Jobs",
    "label": "PERSON",
    "confidence": 1.0
  },
  "relations": [
    {
      "type": "FOUNDED",
      "properties": { "confidence": 0.8 },
      "target": {
        "id": "4:xxx:1",
        "labels": ["ORG"],
        "properties": { "text": "Apple Inc." }
      }
    }
  ]
}
```

### 3. 查询路径

**POST** `/api/v1/kg/query/path`

```bash
curl -X POST http://localhost:8006/api/v1/kg/query/path \
  -H "Content-Type: application/json" \
  -d '{
    "start_entity": "Steve Jobs",
    "end_entity": "Apple Inc.",
    "max_depth": 3
  }'
```

**响应**:

```json
{
  "paths": [
    {
      "nodes": [
        { "text": "Steve Jobs", "labels": ["PERSON"] },
        { "text": "Apple Inc.", "labels": ["ORG"] }
      ],
      "relations": ["FOUNDED"]
    }
  ],
  "count": 1
}
```

### 4. 获取邻居节点

**POST** `/api/v1/kg/query/neighbors`

```bash
curl -X POST http://localhost:8006/api/v1/kg/query/neighbors \
  -H "Content-Type: application/json" \
  -d '{
    "entity": "Apple Inc.",
    "max_neighbors": 10
  }'
```

### 5. 统计信息

**GET** `/api/v1/kg/statistics`

```bash
curl http://localhost:8006/api/v1/kg/statistics
```

**响应**:

```json
{
  "total_nodes": 150,
  "total_relationships": 320,
  "label_statistics": [
    { "label": "PERSON", "count": 45 },
    { "label": "ORG", "count": 60 },
    { "label": "GPE", "count": 35 }
  ]
}
```

### 6. 健康检查

**GET** `/api/v1/kg/health`

```bash
curl http://localhost:8006/api/v1/kg/health
```

**响应**:

```json
{
  "neo4j": {
    "healthy": true,
    "connected": true
  },
  "entity_extractor": {
    "healthy": true,
    "model": "en_core_web_sm"
  },
  "relation_extractor": {
    "healthy": true,
    "model": "en_core_web_sm"
  }
}
```

---

## 🏗️ 架构设计

### 核心模块

```
Knowledge Service
├── Neo4j Client          # 图数据库客户端
├── Entity Extractor      # 实体提取器
├── Relation Extractor    # 关系提取器
└── KG Service           # 知识图谱服务（整合层）
```

### 技术栈

| 组件         | 技术    | 版本    |
| ------------ | ------- | ------- |
| **Web 框架** | FastAPI | 0.109.2 |
| **图数据库** | Neo4j   | 5.16.0  |
| **NLP**      | SpaCy   | 3.7.2   |
| **异步**     | asyncio | -       |

### 实体标签（SpaCy）

| 标签      | 含义         | 示例          |
| --------- | ------------ | ------------- |
| `PERSON`  | 人名         | Steve Jobs    |
| `ORG`     | 组织         | Apple Inc.    |
| `GPE`     | 地理政治实体 | California    |
| `LOC`     | 地点         | Pacific Ocean |
| `DATE`    | 日期         | 1976          |
| `MONEY`   | 货币         | $1000         |
| `PRODUCT` | 产品         | iPhone        |

---

## 📊 性能指标

| 指标         | 预期    | 说明                |
| ------------ | ------- | ------------------- |
| 实体提取速度 | < 500ms | 每段文本（~500 字） |
| 关系提取速度 | < 1s    | 每段文本            |
| 图查询延迟   | < 200ms | 单跳查询            |
| 并发连接     | > 100   | 同时处理的请求      |

---

## 🧪 测试

### 手动测试

使用 Swagger UI 测试:

```
http://localhost:8006/docs
```

### Cypher 查询示例

连接到 Neo4j Browser (`http://localhost:7474`) 并运行：

```cypher
// 查看所有节点
MATCH (n) RETURN n LIMIT 25;

// 查找人物
MATCH (p:PERSON) RETURN p.text, p.confidence LIMIT 10;

// 查找关系
MATCH (a)-[r]->(b)
RETURN a.text, type(r), b.text
LIMIT 20;

// 查找特定路径
MATCH path = (a:PERSON)-[*1..3]-(b:ORG)
WHERE a.text = 'Steve Jobs'
RETURN path;
```

---

## 🔧 配置项

在 `.env` 或环境变量中配置：

| 变量             | 默认值                  | 说明           |
| ---------------- | ----------------------- | -------------- |
| `NEO4J_URI`      | `bolt://localhost:7687` | Neo4j 连接 URI |
| `NEO4J_USER`     | `neo4j`                 | Neo4j 用户名   |
| `NEO4J_PASSWORD` | `password`              | Neo4j 密码     |
| `SPACY_MODEL`    | `en_core_web_sm`        | SpaCy 模型     |
| `LOG_LEVEL`      | `INFO`                  | 日志级别       |
| `PORT`           | `8006`                  | 服务端口       |

---

## 🚀 后续迭代计划

### Phase 2: 增强功能

- [ ] 图谱可视化（D3.js/Cytoscape.js）
- [ ] 增量更新（避免重复节点）
- [ ] 多跳推理
- [ ] 实体消歧

### Phase 3: 高级功能

- [ ] 时序图谱（时间属性）
- [ ] 图嵌入（Node2Vec/GraphSAGE）
- [ ] 联邦图谱查询
- [ ] 知识融合

---

## 📝 注意事项

1. **SpaCy 模型下载**

   - 首次运行前必须下载模型
   - 英文模型：`python -m spacy download en_core_web_sm`
   - 中文模型：`python -m spacy download zh_core_web_sm`

2. **Neo4j 连接**

   - 确保 Neo4j 正常运行
   - 检查端口 7687 是否开放

3. **性能优化**

   - 大批量导入建议使用批处理
   - 定期创建索引优化查询性能

4. **后备方案**
   - 如果 SpaCy 不可用，会使用简单规则提取
   - 功能有限但不会中断服务

---

## 📞 支持

**文档**: 本 README
**API 文档**: `http://localhost:8006/docs`
**Neo4j Browser**: `http://localhost:7474`

---

**版本**: v1.0.0
**最后更新**: 2025-10-27
**状态**: ✅ 完成
