# Sprint 执行指南 - VoiceAssistant 项目

> **当前状态**: 📝 规划完成，准备执行
> **执行周期**: 12 周 (3 个月)
> **开始日期**: 待定
> **项目负责人**: [待指定]

---

## 🎯 执行概览

### 当前项目状态

**✅ 已完成**:

- 代码审查完成 (228 个 TODO 已识别)
- 迭代计划完成 (12 周详细计划)
- VoiceHelper 功能迁移方案完成 (10 项功能)
- 服务级别详细计划完成 (Agent Engine, Voice Engine)

**📝 待执行**:

- Sprint 1 (Week 1-2): P0 核心功能
- Sprint 2-12: 按计划逐步推进

---

## 📋 立即行动清单 (本周)

### Day 1: 项目启动准备

#### 上午 (9:00-12:00)

**任务 1: 团队组建与角色确认** (2 小时)

- [ ] 确认项目负责人 (Tech Lead)
- [ ] 分配 AI Engineer (2 人)
- [ ] 分配 Backend Engineer (2 人)
- [ ] 分配 SRE Engineer (1 人)
- [ ] 可选: Frontend Engineer (1 人, Week 3 开始)
- [ ] 可选: QA Engineer (1 人, Week 5 开始)

**产出**: 团队名单与联系方式表

**任务 2: 环境准备检查清单** (1 小时)

- [ ] 开发环境访问权限
  - GitHub 仓库访问
  - 服务器 SSH 访问
  - 数据库访问权限
- [ ] 必要工具安装确认
  - Go 1.25.0+
  - Python 3.10+
  - Node.js 18+
  - Docker & Docker Compose
  - Kubernetes CLI (kubectl)

**产出**: 环境准备完成确认表

#### 下午 (14:00-18:00)

**任务 3: Sprint 1 启动会** (2 小时)

- [ ] 讲解项目背景与目标
- [ ] 回顾迭代计划文档
  - [SERVICES_ITERATION_MASTER_PLAN.md](SERVICES_ITERATION_MASTER_PLAN.md)
  - [VOICEHELPER_MIGRATION_PLAN.md](VOICEHELPER_MIGRATION_PLAN.md)
- [ ] 明确 Sprint 1 目标
- [ ] 分配 Sprint 1 任务
- [ ] 确定每日站会时间 (建议 10:00 AM)

**产出**: Sprint 1 任务分配表

**任务 4: 基础设施部署规划** (2 小时)

- [ ] 确认基础设施需求
  - Redis Sentinel (3 节点)
  - Milvus (向量数据库)
  - PostgreSQL (主数据库)
  - MinIO (对象存储)
  - Kafka (消息队列)
- [ ] 准备部署脚本
- [ ] 分配部署责任人

**产出**: 基础设施部署计划

---

### Day 2: 基础设施部署

#### 目标

部署 Sprint 1 所需的基础设施

#### Redis 部署

```bash
# 使用 Docker Compose 部署 Redis Sentinel
cd /Users/lintao/important/ai-customer/VoiceAssistant

# 创建 Redis 配置
cat > deployments/docker/redis-sentinel.yaml <<EOF
version: '3.8'

services:
  redis-master:
    image: redis:7-alpine
    container_name: redis-master
    ports:
      - "6379:6379"
    volumes:
      - redis-master-data:/data
    command: redis-server --appendonly yes

  redis-sentinel-1:
    image: redis:7-alpine
    container_name: redis-sentinel-1
    ports:
      - "26379:26379"
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis-sentinel-1.conf:/etc/redis/sentinel.conf

  redis-sentinel-2:
    image: redis:7-alpine
    container_name: redis-sentinel-2
    ports:
      - "26380:26379"
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis-sentinel-2.conf:/etc/redis/sentinel.conf

  redis-sentinel-3:
    image: redis:7-alpine
    container_name: redis-sentinel-3
    ports:
      - "26381:26379"
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis-sentinel-3.conf:/etc/redis/sentinel.conf

volumes:
  redis-master-data:
EOF

# 启动 Redis
docker-compose -f deployments/docker/redis-sentinel.yaml up -d

# 验证
redis-cli ping  # 应返回 PONG
```

**验收**:

- [ ] Redis 服务正常运行
- [ ] Sentinel 集群健康
- [ ] 可以读写数据

#### Milvus 部署

```bash
# 下载 Milvus standalone 配置
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O deployments/docker/milvus.yaml

# 启动 Milvus
docker-compose -f deployments/docker/milvus.yaml up -d

# 等待启动 (约 30 秒)
sleep 30

# 验证
curl http://localhost:9091/healthz  # 应返回 OK
```

**验收**:

- [ ] Milvus 服务正常运行
- [ ] Attu (Web UI) 可访问 http://localhost:3000
- [ ] 可以创建 collection

#### PostgreSQL 部署

```bash
# 使用现有配置或创建新配置
cat > deployments/docker/postgres.yaml <<EOF
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: voiceassistant-postgres
    environment:
      POSTGRES_DB: voiceassistant
      POSTGRES_USER: voiceassistant
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./migrations/postgres:/docker-entrypoint-initdb.d

volumes:
  postgres-data:
EOF

# 启动 PostgreSQL
docker-compose -f deployments/docker/postgres.yaml up -d

# 验证
psql -h localhost -U voiceassistant -d voiceassistant -c "SELECT version();"
```

**验收**:

- [ ] PostgreSQL 服务正常运行
- [ ] 数据库可连接
- [ ] 初始化脚本执行成功

#### 环境变量配置

```bash
# 创建环境变量文件
cat > .env.local <<EOF
# Redis
REDIS_URL=redis://localhost:6379/0

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=voiceassistant
POSTGRES_USER=voiceassistant
POSTGRES_PASSWORD=changeme

# Model Adapter
OPENAI_API_KEY=your_openai_key_here
CLAUDE_API_KEY=your_claude_key_here

# MinIO (可选)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Kafka (可选)
KAFKA_BROKERS=localhost:9092
EOF

echo "✅ 环境变量配置完成"
echo "⚠️  请修改 .env.local 中的敏感信息"
```

**验收**:

- [ ] 环境变量文件创建完成
- [ ] 所有服务连接信息正确
- [ ] API 密钥已配置

---

### Day 3-4: Sprint 1 任务 1 - 流式 ASR 识别

#### 负责人

AI Engineer 1

#### 任务分解

**Day 3 上午: WebSocket 端点实现**

```bash
# 1. 创建 WebSocket 路由
cd algo/voice-engine

# 2. 实现代码 (参考 VOICEHELPER_MIGRATION_PLAN.md)
# 文件: app/routers/asr.py
# 复制文档中的完整代码

# 3. 安装依赖
pip install websockets webrtcvad

# 4. 本地测试
python -m pytest tests/test_streaming_asr.py -v
```

**Day 3 下午: VAD 集成**

```bash
# 1. 下载 Silero VAD 模型
mkdir -p models
wget https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.jit -O models/silero_vad.jit

# 2. 实现 VAD 服务
# 文件: app/services/streaming_asr_service.py

# 3. 单元测试
pytest tests/test_vad.py -v
```

**Day 4 上午: Whisper 集成**

```bash
# 1. 安装 Faster-Whisper
pip install faster-whisper

# 2. 下载模型
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# 3. 实现流式识别逻辑
# 参考文档中的代码

# 4. 测试
pytest tests/test_whisper_streaming.py -v
```

**Day 4 下午: 前端客户端**

```bash
# 1. 创建前端组件
cd platforms/web

# 2. 实现 StreamingASRClient.tsx
# 复制文档中的代码

# 3. 安装依赖
npm install

# 4. 本地测试
npm run dev
# 访问 http://localhost:3000/test/asr
```

#### 验收标准

**技术验收**:

- [ ] WebSocket 连接稳定
- [ ] VAD 端点检测准确率 > 95%
- [ ] 增量识别延迟 < 500ms
- [ ] 最终识别准确率 > 90%
- [ ] 并发支持 > 20 连接

**测试验收**:

```bash
# 运行完整测试套件
cd algo/voice-engine
pytest tests/ -v --cov=app --cov-report=html

# 压力测试
python tests/load/test_streaming_asr_load.py --connections 50 --duration 60
```

**演示验收**:

- [ ] 实时语音识别演示
- [ ] 断线重连演示
- [ ] 多用户并发演示

---

### Day 5-7: Sprint 1 任务 2 - 长期记忆衰减

#### 负责人

AI Engineer 1

#### 任务分解

**Day 5: Milvus 集成**

```bash
cd algo/agent-engine

# 1. 安装依赖
pip install pymilvus numpy

# 2. 实现向量记忆管理器
# 文件: app/memory/vector_memory_manager.py
# 复制文档中的完整代码

# 3. 初始化 Milvus collection
python scripts/init_milvus_memory.py

# 4. 单元测试
pytest tests/test_vector_memory.py -v
```

**Day 6: Ebbinghaus 衰减算法**

```bash
# 1. 实现时间衰减逻辑
# 已在 vector_memory_manager.py 中实现

# 2. 实现访问频率增强
# 已在 vector_memory_manager.py 中实现

# 3. 算法验证测试
pytest tests/test_memory_decay.py -v

# 4. 可视化衰减曲线
python scripts/visualize_decay_curve.py
```

**Day 7: 集成到 Agent**

```bash
# 1. 实现统一记忆管理器
# 文件: app/memory/memory_manager.py

# 2. 集成到 Agent Service
# 文件: app/core/agent_service.py

# 3. API 接口
# 文件: routers/memory.py

# 4. 端到端测试
pytest tests/integration/test_agent_memory.py -v
```

#### 验收标准

**技术验收**:

- [ ] 记忆成功存储到 Milvus
- [ ] 向量检索召回率 > 80%
- [ ] 时间衰减机制生效 (30 天半衰期)
- [ ] 访问频率增强生效
- [ ] 重要性评分合理

**功能验收**:

```bash
# 测试记忆存储
curl -X POST http://localhost:8000/api/v1/memory/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "content": "我喜欢吃北京烤鸭",
    "auto_evaluate_importance": true
  }'

# 测试记忆召回
curl -X POST http://localhost:8000/api/v1/memory/recall \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "query": "你知道我喜欢吃什么吗？",
    "top_k": 5
  }'
```

---

### Week 2: Sprint 1 完成与验收

#### Day 8-9: 集成测试与优化

**任务清单**:

- [ ] 流式 ASR + Agent 记忆集成测试
- [ ] 性能优化
- [ ] 文档更新
- [ ] Bug 修复

**集成测试场景**:

```python
# tests/integration/test_sprint1_integration.py

async def test_voice_to_memory_flow():
    """测试: 语音 → ASR → Agent → 记忆存储"""

    # 1. 发送语音数据到流式 ASR
    async with websockets.connect('ws://localhost:8001/ws/asr/stream') as ws:
        await ws.send(json.dumps({
            'model_size': 'base',
            'language': 'zh'
        }))

        # 发送音频数据
        with open('test_audio.wav', 'rb') as f:
            audio_data = f.read()
            await ws.send(audio_data)

        # 接收识别结果
        result = await ws.recv()
        text = json.loads(result)['text']

        assert text is not None

    # 2. 将识别文本存储到记忆
    response = requests.post(
        'http://localhost:8000/api/v1/memory/store',
        json={
            'user_id': 'test_user',
            'content': text
        }
    )

    assert response.status_code == 200
    memory_id = response.json()['memory_id']

    # 3. 验证记忆可召回
    response = requests.post(
        'http://localhost:8000/api/v1/memory/recall',
        json={
            'user_id': 'test_user',
            'query': text[:20]  # 使用前 20 个字符查询
        }
    )

    assert response.status_code == 200
    memories = response.json()['memories']
    assert len(memories) > 0
    assert text in memories[0]
```

#### Day 10: Sprint 1 演示与回顾

**演示准备**:

1. 准备演示环境
2. 准备演示数据
3. 准备演示脚本

**演示内容**:

- **功能 1**: 实时语音识别演示

  - 展示流式识别效果
  - 展示 VAD 端点检测
  - 展示增量 + 最终识别

- **功能 2**: Agent 长期记忆演示
  - 展示记忆存储
  - 展示记忆召回
  - 展示时间衰减效果

**Sprint 回顾会议** (2 小时):

- 回顾 Sprint 1 目标完成情况
- 讨论遇到的问题和解决方案
- 收集改进建议
- 规划 Sprint 2

**产出**:

- Sprint 1 完成报告
- Sprint 2 任务分配表
- 风险与问题清单

---

## 📊 Sprint 1 验收清单

### 流式 ASR 识别

**功能验收**:

- [ ] WebSocket 端点可访问
- [ ] 可以建立稳定连接
- [ ] 支持音频流传输
- [ ] VAD 端点检测正常
- [ ] 增量识别返回中间结果
- [ ] 最终识别返回完整结果
- [ ] 支持多种语言 (中文/英文)

**性能验收**:

- [ ] 增量识别延迟 < 500ms
- [ ] 最终识别准确率 > 90%
- [ ] VAD 准确率 > 95%
- [ ] 并发支持 > 20 连接
- [ ] 内存占用合理 (< 2GB per instance)

**代码质量**:

- [ ] 单元测试覆盖率 > 70%
- [ ] 代码通过 Lint 检查
- [ ] 有完整的类型注解
- [ ] 有详细的文档注释

**文档验收**:

- [ ] API 文档完整
- [ ] 配置文档完整
- [ ] 故障排查指南
- [ ] 性能调优指南

---

### 长期记忆衰减

**功能验收**:

- [ ] 记忆可以存储到 Milvus
- [ ] 记忆可以检索
- [ ] 时间衰减生效
- [ ] 访问频率增强生效
- [ ] 重要性评分合理
- [ ] 支持多用户隔离

**性能验收**:

- [ ] 存储延迟 < 100ms
- [ ] 检索延迟 < 200ms
- [ ] 召回率 > 80%
- [ ] 准确率 > 85%
- [ ] 支持 10k+ 记忆

**代码质量**:

- [ ] 单元测试覆盖率 > 70%
- [ ] 代码通过 Lint 检查
- [ ] 有完整的类型注解
- [ ] 有详细的文档注释

**文档验收**:

- [ ] API 文档完整
- [ ] 算法文档完整
- [ ] 配置文档完整
- [ ] 性能指标文档

---

## 📅 Sprint 2-12 概览

### Sprint 2 (Week 3-4): 基础设施增强

**目标**: 任务持久化 + 限流 + 服务发现

**关键任务**:

1. Redis 任务持久化 (2-3 天, Backend Eng 2)
2. 分布式限流器 (2-3 天, Backend Eng 1)
3. Consul 服务发现 (4-5 天, SRE)

**验收**: 任务持久化，限流生效，服务自动发现

---

### Sprint 3 (Week 5-6): 模型与知识管理

**目标**: GLM-4 + 文档版本管理

**关键任务**:

1. GLM-4 适配器 (2 天, Backend Eng 1)
2. 文档版本管理 (3-4 天, Backend Eng 2)

**验收**: GLM-4 可用，文档版本正常

---

### Sprint 4 (Week 7-8): 安全与通知

**目标**: 病毒扫描 + Push 通知

**关键任务**:

1. ClamAV 集成 (2-3 天, Backend Eng 2)
2. Push 通知 (3-4 天, Backend Eng 1)

**验收**: 病毒扫描生效，推送通知可用

---

### Sprint 5-6 (Week 9-12): 可观测性与前端

**目标**: 监控 + 追踪 + 前端应用

**关键任务**:

1. Prometheus 指标 (Week 9)
2. Jaeger 追踪 (Week 10)
3. Grafana 仪表盘 (Week 11)
4. Web 前端 (Week 9-11)

**验收**: 完整监控体系，前端应用可用

---

## 🛠️ 开发工具与最佳实践

### Git 工作流

```bash
# 1. 创建功能分支
git checkout -b feature/sprint1-streaming-asr

# 2. 开发与提交
git add .
git commit -m "feat(voice): implement streaming ASR with WebSocket

- Add WebSocket endpoint for streaming ASR
- Integrate Silero VAD for endpoint detection
- Implement incremental and final recognition
- Add frontend client component

Refs: #sprint1-task1"

# 3. 推送与创建 PR
git push origin feature/sprint1-streaming-asr
# 在 GitHub 上创建 Pull Request

# 4. Code Review 后合并
git checkout main
git pull origin main
git branch -d feature/sprint1-streaming-asr
```

### 代码质量检查

```bash
# Python (Voice Engine, Agent Engine)
cd algo/voice-engine
ruff check .
ruff format .
mypy app/
pytest tests/ --cov=app --cov-report=html

# Go (Services)
cd cmd/knowledge-service
golangci-lint run ./...
go test ./... -race -cover

# TypeScript (Frontend)
cd platforms/web
npm run lint
npm run type-check
npm test
```

### 每日站会模板

**时间**: 每天 10:00 AM (15 分钟)

**格式**:

1. 昨天完成了什么？
2. 今天计划做什么？
3. 有什么阻碍？

**示例**:

```
张三 (AI Eng 1):
- 昨天: 完成 WebSocket 端点实现，通过单元测试
- 今天: 集成 VAD，开始流式识别逻辑
- 阻碍: Whisper 模型下载较慢，需要镜像

李四 (AI Eng 2):
- 昨天: 研究 Milvus API，设计数据模型
- 今天: 实现向量记忆管理器
- 阻碍: 无

SRE (王五):
- 昨天: 部署 Redis 和 Milvus
- 今天: 配置监控和日志
- 阻碍: 无
```

---

## 📈 进度追踪

### 每周报告模板

```markdown
# Sprint 1 - Week 1 周报

## 完成情况

### 流式 ASR 识别 (60%)

- ✅ WebSocket 端点实现
- ✅ VAD 集成
- 🔄 Whisper 集成中
- ⏳ 前端客户端待开始

### 长期记忆衰减 (30%)

- ✅ Milvus 环境部署
- 🔄 向量管理器实现中
- ⏳ 衰减算法待实现
- ⏳ Agent 集成待开始

## 遇到的问题

1. **Whisper 模型下载慢**

   - 影响: 延迟 1 天
   - 解决方案: 使用国内镜像

2. **Milvus 连接不稳定**
   - 影响: 测试不稳定
   - 解决方案: 增加重试机制

## 下周计划

- 完成流式 ASR 所有功能
- 完成长期记忆 70% 功能
- 开始集成测试

## 风险提示

- ⚠️ 前端工程师还未到位，可能影响演示
- ⚠️ 测试覆盖率偏低，需要补充测试用例
```

---

## 🎯 关键里程碑

| 里程碑         | 日期         | 交付物              | 验收标准            |
| -------------- | ------------ | ------------------- | ------------------- |
| Sprint 1 完成  | Week 2 结束  | 流式 ASR + 长期记忆 | 演示通过 + 测试通过 |
| Sprint 4 完成  | Week 8 结束  | MVP 完整功能        | 端到端演示          |
| Sprint 8 完成  | Week 16 结束 | 性能达标            | 压测通过            |
| Sprint 12 完成 | Week 24 结束 | 生产就绪            | 准生产验证          |

---

## 📞 联系方式

### 项目团队

| 角色          | 姓名   | 邮箱 | 职责                  |
| ------------- | ------ | ---- | --------------------- |
| Tech Lead     | [待定] | -    | 整体规划与技术决策    |
| AI Eng 1      | [待定] | -    | 流式 ASR + 长期记忆   |
| AI Eng 2      | [待定] | -    | RAG 优化              |
| Backend Eng 1 | [待定] | -    | 限流 + GLM-4          |
| Backend Eng 2 | [待定] | -    | 任务持久化 + 文档版本 |
| SRE           | [待定] | -    | 基础设施 + 监控       |

### 会议安排

- **每日站会**: 10:00 AM (15 分钟)
- **Sprint 回顾**: 每 2 周五下午 (1 小时)
- **技术债务审查**: 每周三下午 (30 分钟)

---

## 🔗 相关文档

- [总体迭代计划](SERVICES_ITERATION_MASTER_PLAN.md)
- [VoiceHelper 迁移计划](VOICEHELPER_MIGRATION_PLAN.md)
- [Agent Engine 详细计划](SERVICE_AGENT_ENGINE_PLAN.md)
- [Voice Engine 详细计划](SERVICE_VOICE_ENGINE_PLAN.md)
- [执行摘要](SERVICES_REVIEW_EXECUTIVE_SUMMARY.md)

---

**准备好开始了吗？让我们开始 Sprint 1！🚀**

**下一步**:

1. 组建团队
2. 部署基础设施
3. 启动 Sprint 1

---

**文档版本**: v1.0.0
**创建日期**: 2025-10-27
**最后更新**: 2025-10-27
