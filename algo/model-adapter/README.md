# Model Adapter Service

统一的 LLM 提供商适配层，支持多个模型提供商的接入和管理。

## 🎯 核心功能

- **多提供商支持**: OpenAI, Claude (Anthropic), 智谱AI, 通义千问, 百度文心, Azure OpenAI
- **统一接口**: 标准化的 Chat Completion API
- **流式/非流式**: 支持两种响应模式
- **成本计算**: 自动计算 Token 使用量和成本
- **监控**: Prometheus 指标 + OpenTelemetry 追踪
- **生命周期管理**: 优雅启停和健康检查

## 📁 项目结构

```
algo/model-adapter/
├── app/
│   ├── adapters/          # 各提供商适配器实现
│   │   ├── openai_adapter.py
│   │   ├── claude_adapter.py
│   │   ├── zhipu_adapter.py
│   │   └── ...
│   ├── core/              # 核心组件
│   │   ├── adapter_manager.py    # 适配器管理器
│   │   ├── base_adapter.py       # 适配器基类
│   │   ├── cost_calculator.py    # 成本计算器
│   │   ├── settings.py           # 配置管理
│   │   └── exceptions.py         # 异常定义
│   ├── routers/           # API 路由
│   │   ├── chat.py
│   │   ├── embedding.py
│   │   └── health.py
│   ├── services/          # 业务服务
│   │   ├── adapter_service.py
│   │   └── cache_service.py
│   └── middleware/        # 中间件
│       └── error_handler.py
├── tests/                 # 测试
│   ├── test_adapter_manager.py
│   └── test_exceptions.py
├── main.py               # 入口文件
├── requirements.txt      # 依赖
├── Dockerfile           # 容器镜像
├── docker-compose.yml   # 本地开发环境
└── OPTIMIZATION.md      # 优化方案 (⭐ 必读)
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/model-adapter

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

创建 `.env` 文件:

```bash
# 应用配置
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8005

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选

# Claude (Anthropic)
ANTHROPIC_API_KEY=sk-ant-...

# 智谱AI
ZHIPU_API_KEY=...

# 通义千问 (DashScope)
DASHSCOPE_API_KEY=...

# 百度文心
BAIDU_API_KEY=...
BAIDU_SECRET_KEY=...

# 监控
ENABLE_METRICS=true
ENABLE_TRACING=false
```

### 3. 启动服务

```bash
# 开发模式 (热重载)
uvicorn main:app --reload --host 0.0.0.0 --port 8005

# 或使用 Make
make dev

# 或使用 Docker Compose
docker-compose up -d
```

### 4. 验证

```bash
# 健康检查
curl http://localhost:8005/health

# 查看支持的模型
curl http://localhost:8005/v1/models

# 聊天完成 (非流式)
curl -X POST http://localhost:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7
  }'

# 流式响应
curl -X POST http://localhost:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## 📊 监控

### Prometheus 指标

访问: http://localhost:8005/metrics

主要指标:
- `http_requests_total`: 请求总数
- `http_request_duration_seconds`: 请求延迟
- (更多指标见 Phase 4 优化)

### OpenTelemetry 追踪

配置 `OTEL_ENDPOINT` 后可将 Trace 发送到 Jaeger/Zipkin。

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 测试覆盖率
pytest --cov=app --cov-report=html
open htmlcov/index.html

# 单个测试文件
pytest tests/test_adapter_manager.py -v
```

## 📈 API 文档

启动服务后访问:
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc

## 🔧 开发

### 添加新的提供商

1. 创建适配器: `app/adapters/new_provider_adapter.py`

```python
from app.core.base_adapter import BaseAdapter, AdapterResponse

class NewProviderAdapter(BaseAdapter):
    def __init__(self, api_key: str):
        super().__init__(provider="new_provider")
        self.api_key = api_key

    async def generate(self, model: str, messages: list, **kwargs):
        # 实现生成逻辑
        pass

    async def generate_stream(self, model: str, messages: list, **kwargs):
        # 实现流式生成
        pass

    async def health_check(self) -> bool:
        # 实现健康检查
        return True
```

2. 注册到 `AdapterManager`: `app/core/adapter_manager.py`

```python
# 在 initialize() 方法中添加
if self.settings.new_provider_api_key:
    from app.adapters.new_provider_adapter import NewProviderAdapter
    self._adapters["new_provider"] = NewProviderAdapter(
        api_key=self.settings.new_provider_api_key
    )
```

3. 更新配置: `app/core/settings.py`

```python
new_provider_api_key: str | None = Field(default=None, env="NEW_PROVIDER_API_KEY")
new_provider_enabled: bool = Field(default=True, env="NEW_PROVIDER_ENABLED")
```

## ⚠️ 已知问题与优化计划

### 关键问题

当前版本 (v1.0.0) 存在以下待优化点:

1. **稳定性 (P0)** ⚠️
   - ❌ 无重试机制 (Provider 故障时直接失败)
   - ❌ 无熔断器 (Circuit Breaker)
   - ❌ 流式响应错误恢复能力弱

2. **性能 (P1)**
   - ❌ 缓存服务未集成 (cache_service.py 闲置)
   - ❌ Token 估算精度低 (~20% 误差)

3. **成本 (P1)**
   - ❌ 无智能路由 (无法根据成本自动选模型)
   - ❌ 无成本预算告警

4. **安全 (P1)**
   - ❌ API Key 明文存环境变量
   - ❌ 无 PII 脱敏

5. **测试 (P1)**
   - ❌ 覆盖率 <15%

### 📋 优化路线图

**详见**: [OPTIMIZATION.md](./OPTIMIZATION.md)

**6 个 Phase, 15 个 Task, ~40 人日 (1.5-2 个月)**

优先级:
1. **Week 1-2**: 稳定性 (重试 + 熔断) - P0 🔥
2. **Week 3-4**: 性能 (缓存 + tiktoken + 批处理) - P1
3. **Week 5**: 成本控制 (智能路由 + 预算告警) - P1
4. **Week 6**: 可观测性 (Trace + 指标) - P1
5. **Week 7**: 安全 (Vault + 脱敏) - P1
6. **Week 8**: 测试 (覆盖率 >70%) - P1

### 🚀 立即开始

```bash
# 1. 创建 GitHub Issues
./scripts/create_model_adapter_issues.sh

# 2. 开始第一个任务
git checkout -b feat/model-adapter-retry-circuit-breaker
pip install tenacity pybreaker
# 编辑 app/core/base_adapter.py...
```

## 📚 相关文档

- **优化方案**: [OPTIMIZATION.md](./OPTIMIZATION.md) - 快速启动指南
- **完整 Roadmap**: [docs/roadmap/model-adapter-optimization.md](../../docs/roadmap/model-adapter-optimization.md)
- **Issue 脚本**: [scripts/create_model_adapter_issues.sh](../../scripts/create_model_adapter_issues.sh)
- **架构设计**: [docs/arch/overview.md](../../docs/arch/overview.md)
- **Runbook**: [docs/runbook/index.md](../../docs/runbook/index.md)

## 🔗 依赖服务

- Redis (可选): 缓存 (如启用)
- ClickHouse (可选): 成本追踪 (Phase 3 后)
- Jaeger/Zipkin (可选): 分布式追踪 (Phase 4 后)
- Vault/KMS (可选): 密钥管理 (Phase 5 后)

## 📞 支持

- **Owner**: AI-Orchestrator Team
- **Issues**: GitHub Issues (标签: `area/model-adapter`)
- **Slack**: #ai-orchestrator

## 📄 许可

MIT License

---

**版本**: v1.0.0
**最后更新**: 2025-11-01
