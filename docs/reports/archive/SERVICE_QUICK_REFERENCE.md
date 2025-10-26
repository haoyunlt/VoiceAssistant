# 服务快速参考

## Go 服务快速启动

### Identity Service

```bash
cd cmd/identity-service
make deps && make docker-compose-up
# 访问: http://localhost:8000
```

### Conversation Service

```bash
cd cmd/conversation-service
make deps && make docker-compose-up
# 访问: http://localhost:8001
```

### Knowledge Service

```bash
cd cmd/knowledge-service
make deps && make docker-compose-up
# 访问: http://localhost:8002
```

### AI Orchestrator

```bash
cd cmd/ai-orchestrator
make deps && make docker-compose-up
# 访问: http://localhost:8003
```

### Model Router

```bash
cd cmd/model-router
make deps && make docker-compose-up
# 访问: http://localhost:8004
```

### Notification Service

```bash
cd cmd/notification-service
make deps && make docker-compose-up
# 访问: http://localhost:8005
```

### Analytics Service

```bash
cd cmd/analytics-service
make deps && make docker-compose-up
# 访问: http://localhost:8006
```

## Python 服务快速启动

### Agent Engine

```bash
cd algo/agent-engine
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8010
```

### Indexing Service

```bash
cd algo/indexing-service
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8011
```

### Retrieval Service

```bash
cd algo/retrieval-service
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8012
```

### Model Adapter

```bash
cd algo/model-adapter
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8013
```

### RAG Engine

```bash
cd algo/rag-engine
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8014
```

### Voice Engine

```bash
cd algo/voice-engine
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8015
```

### Multimodal Engine

```bash
cd algo/multimodal-engine
./setup-venv.sh && docker-compose up -d
# 访问: http://localhost:8016
```

## 常用命令

### Go 服务

```bash
make build          # 构建
make run            # 运行
make test           # 测试
make docker-build   # Docker 构建
make docker-compose-up    # 启动服务栈
make docker-compose-down  # 停止服务栈
```

### Python 服务

```bash
source venv/bin/activate  # 激活虚拟环境
uvicorn main:app --reload # 运行（开发模式）
docker-compose up -d      # 启动服务栈
docker-compose down       # 停止服务栈
```

## 端口映射

| 服务                 | 端口       | 类型       |
| -------------------- | ---------- | ---------- |
| identity-service     | 9000, 8000 | gRPC, HTTP |
| conversation-service | 9001, 8001 | gRPC, HTTP |
| knowledge-service    | 9002, 8002 | gRPC, HTTP |
| ai-orchestrator      | 9003, 8003 | gRPC, HTTP |
| model-router         | 9004, 8004 | gRPC, HTTP |
| notification-service | 9005, 8005 | gRPC, HTTP |
| analytics-service    | 9006, 8006 | gRPC, HTTP |
| agent-engine         | 8010       | HTTP       |
| indexing-service     | 8011       | HTTP       |
| retrieval-service    | 8012       | HTTP       |
| model-adapter        | 8013       | HTTP       |
| rag-engine           | 8014       | HTTP       |
| voice-engine         | 8015       | HTTP       |
| multimodal-engine    | 8016       | HTTP       |
