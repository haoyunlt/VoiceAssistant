# Week 1 行动计划（P0 阻塞项解决）

> **时间**: Week 1 (Day 1-5)
> **目标**: 解决所有 P0 阻塞项，让所有服务可启动
> **优先级**: 最高 🔥

---

## 📋 任务概览

| 任务                     | 优先级 | 预计时间 | 负责人    | 状态    |
| ------------------------ | ------ | -------- | --------- | ------- |
| Task 1.1: Wire 代码生成  | P0     | 2 天     | Backend 1 | ⬜ TODO |
| Task 1.2: Proto 代码生成 | P0     | 1 天     | Backend 1 | ⬜ TODO |
| Task 1.3: 服务启动验证   | P0     | 1 天     | SRE       | ⬜ TODO |
| Task 1.4: MinIO 集成     | P1     | 2 天     | Backend 2 | ⬜ TODO |

---

## Day 1: Wire 代码生成

### Task 1.1: Wire 代码生成 (P0)

**目标**: 为所有 7 个 Go 服务生成 `wire_gen.go`

#### 步骤

##### 1. 安装 Wire 工具

```bash
# 安装 Wire
go install github.com/google/wire/cmd/wire@latest

# 验证安装
wire --version
# 应该输出: wire: v0.5.0 或更高版本
```

##### 2. 生成 Identity Service

```bash
cd cmd/identity-service
wire
# 验证生成
ls -la wire_gen.go
# 验证编译
go build .
```

**预期输出**: `wire_gen.go` 文件生成，编译无错误

##### 3. 生成 Conversation Service

```bash
cd ../conversation-service
wire
go build .
```

##### 4. 生成 Knowledge Service

```bash
cd ../knowledge-service
wire
go build .
```

##### 5. 生成 AI Orchestrator

```bash
cd ../ai-orchestrator
wire
go build .
```

##### 6. 生成 Model Router

```bash
cd ../model-router
wire
go build .
```

##### 7. 生成 Notification Service

```bash
cd ../notification-service
wire
go build .
```

##### 8. 生成 Analytics Service

```bash
cd ../analytics-service
wire
go build .
```

##### 9. 统一验证

```bash
# 回到项目根目录
cd ../../

# 创建 Makefile 任务 (如果不存在)
cat >> Makefile << 'EOF'

.PHONY: wire-gen
wire-gen:
	@echo "Generating Wire code for all services..."
	@cd cmd/identity-service && wire
	@cd cmd/conversation-service && wire
	@cd cmd/knowledge-service && wire
	@cd cmd/ai-orchestrator && wire
	@cd cmd/model-router && wire
	@cd cmd/notification-service && wire
	@cd cmd/analytics-service && wire
	@echo "Wire generation complete!"

.PHONY: build-all
build-all:
	@echo "Building all Go services..."
	@cd cmd/identity-service && go build -o ../../bin/identity-service .
	@cd cmd/conversation-service && go build -o ../../bin/conversation-service .
	@cd cmd/knowledge-service && go build -o ../../bin/knowledge-service .
	@cd cmd/ai-orchestrator && go build -o ../../bin/ai-orchestrator .
	@cd cmd/model-router && go build -o ../../bin/model-router .
	@cd cmd/notification-service && go build -o ../../bin/notification-service .
	@cd cmd/analytics-service && go build -o ../../bin/analytics-service .
	@echo "Build complete! Binaries in ./bin/"
EOF

# 运行
make wire-gen
make build-all
```

**验收标准**:

- [ ] 所有服务目录下存在 `wire_gen.go` 文件
- [ ] `make build-all` 成功，无编译错误
- [ ] `bin/` 目录下有 7 个可执行文件

---

## Day 2: Proto 代码生成

### Task 1.2: Proto 代码生成 (P0)

**目标**: 生成 Go 和 Python 的 gRPC 代码

#### 步骤

##### 1. 安装 protoc 和插件

```bash
# 安装 protoc (macOS)
brew install protobuf

# 验证
protoc --version
# 应该输出: libprotoc 3.21.0 或更高版本

# 安装 Go 插件
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# 验证插件
which protoc-gen-go
which protoc-gen-go-grpc

# 安装 Python 插件
pip install grpcio-tools
```

##### 2. 更新 proto-gen.sh 脚本

```bash
cat > scripts/proto-gen.sh << 'EOF'
#!/bin/bash

set -e

PROJECT_ROOT=$(pwd)
PROTO_DIR="${PROJECT_ROOT}/api/proto"
GO_OUT_DIR="${PROJECT_ROOT}/api/proto"

echo "Generating Go proto code..."

# Identity Service
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/identity/v1/identity.proto

# Conversation Service
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/conversation/v1/conversation.proto

# Knowledge Service
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/knowledge/v1/knowledge.proto

# AI Orchestrator
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/ai-orchestrator/v1/orchestrator.proto

# Model Router
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/model-router/v1/model_router.proto

# Events
protoc --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    -I=${PROTO_DIR} \
    ${PROTO_DIR}/events/v1/*.proto

echo "Go proto generation complete!"

echo "Generating Python proto code..."

# Python proto for each AI service
PYTHON_SERVICES=("agent-engine" "rag-engine" "voice-engine" "retrieval-service" "indexing-service" "multimodal-engine" "model-adapter")

for service in "${PYTHON_SERVICES[@]}"; do
    SERVICE_DIR="${PROJECT_ROOT}/algo/${service}"
    PROTO_OUT_DIR="${SERVICE_DIR}/app/protos"

    echo "Generating Python proto for ${service}..."

    mkdir -p ${PROTO_OUT_DIR}

    python -m grpc_tools.protoc \
        -I=${PROTO_DIR} \
        --python_out=${PROTO_OUT_DIR} \
        --grpc_python_out=${PROTO_OUT_DIR} \
        ${PROTO_DIR}/identity/v1/identity.proto \
        ${PROTO_DIR}/conversation/v1/conversation.proto \
        ${PROTO_DIR}/knowledge/v1/knowledge.proto \
        ${PROTO_DIR}/ai-orchestrator/v1/orchestrator.proto \
        ${PROTO_DIR}/model-router/v1/model_router.proto \
        ${PROTO_DIR}/events/v1/*.proto

    # Create __init__.py
    touch ${PROTO_OUT_DIR}/__init__.py
done

echo "Python proto generation complete!"
EOF

chmod +x scripts/proto-gen.sh
```

##### 3. 运行脚本

```bash
./scripts/proto-gen.sh
```

##### 4. 验证 Go proto

```bash
# 检查生成的文件
ls -la api/proto/identity/v1/*.pb.go
ls -la api/proto/conversation/v1/*.pb.go
ls -la api/proto/knowledge/v1/*.pb.go
# ... 其他服务

# 测试导入
cd cmd/identity-service
go build .
```

##### 5. 验证 Python proto

```bash
# 检查生成的文件
ls -la algo/rag-engine/app/protos/*_pb2.py
ls -la algo/rag-engine/app/protos/*_pb2_grpc.py

# 测试导入
cd algo/rag-engine
python -c "from app.protos import identity_pb2; print('Import success')"
```

**验收标准**:

- [ ] 所有 Go proto 文件生成: `api/proto/*/v1/*.pb.go`
- [ ] 所有 Python proto 文件生成: `algo/*/app/protos/*_pb2.py`
- [ ] Go 服务可以导入 proto: `import pb "voiceassistant/api/proto/..."`
- [ ] Python 服务可以导入 proto: `from app.protos import ...`

---

## Day 3: 服务启动验证

### Task 1.3: 服务启动验证 (P0)

**目标**: 启动所有基础设施和服务，验证健康检查

#### 步骤

##### 1. 启动基础设施

```bash
# 启动所有依赖服务
make dev-up

# 或直接使用 docker-compose
docker-compose up -d

# 验证服务状态
docker-compose ps

# 应该看到以下服务运行:
# - postgres
# - redis
# - kafka
# - zookeeper
# - milvus
# - neo4j
# - clickhouse
# - minio
# - consul (可选)
# - prometheus
# - grafana
# - jaeger
```

##### 2. 验证基础设施

```bash
# PostgreSQL
docker exec -it voiceassistant-postgres-1 psql -U postgres -c "SELECT version();"

# Redis
docker exec -it voiceassistant-redis-1 redis-cli ping
# 应该返回: PONG

# Kafka
docker exec -it voiceassistant-kafka-1 kafka-topics.sh --bootstrap-server localhost:9092 --list

# MinIO
curl http://localhost:9000/minio/health/live
# 应该返回: 200 OK
```

##### 3. 启动 Go 服务 (逐个)

**Identity Service**:

```bash
cd cmd/identity-service
go run . &
IDENTITY_PID=$!

# 等待启动
sleep 5

# 健康检查
curl http://localhost:8081/health
# 应该返回: {"status":"ok"}

echo "Identity Service started with PID: $IDENTITY_PID"
```

**Conversation Service**:

```bash
cd ../conversation-service
go run . &
CONVERSATION_PID=$!
sleep 5
curl http://localhost:8082/health
echo "Conversation Service started with PID: $CONVERSATION_PID"
```

**Knowledge Service**:

```bash
cd ../knowledge-service
go run . &
KNOWLEDGE_PID=$!
sleep 5
curl http://localhost:8083/health
echo "Knowledge Service started with PID: $KNOWLEDGE_PID"
```

**AI Orchestrator**:

```bash
cd ../ai-orchestrator
go run . &
ORCHESTRATOR_PID=$!
sleep 5
curl http://localhost:8084/health
echo "AI Orchestrator started with PID: $ORCHESTRATOR_PID"
```

**Model Router**:

```bash
cd ../model-router
go run . &
MODEL_ROUTER_PID=$!
sleep 5
curl http://localhost:8085/health
echo "Model Router started with PID: $MODEL_ROUTER_PID"
```

**Notification Service**:

```bash
cd ../notification-service
go run . &
NOTIFICATION_PID=$!
sleep 5
curl http://localhost:8086/health
echo "Notification Service started with PID: $NOTIFICATION_PID"
```

**Analytics Service**:

```bash
cd ../analytics-service
go run . &
ANALYTICS_PID=$!
sleep 5
curl http://localhost:8087/health
echo "Analytics Service started with PID: $ANALYTICS_PID"
```

##### 4. 启动 Python 服务 (逐个)

**Indexing Service**:

```bash
cd ../../algo/indexing-service
uvicorn main:app --host 0.0.0.0 --port 8011 &
INDEXING_PID=$!
sleep 5
curl http://localhost:8011/health
echo "Indexing Service started with PID: $INDEXING_PID"
```

**Retrieval Service**:

```bash
cd ../retrieval-service
uvicorn main:app --host 0.0.0.0 --port 8012 &
RETRIEVAL_PID=$!
sleep 5
curl http://localhost:8012/health
echo "Retrieval Service started with PID: $RETRIEVAL_PID"
```

**RAG Engine**:

```bash
cd ../rag-engine
uvicorn main:app --host 0.0.0.0 --port 8006 &
RAG_PID=$!
sleep 5
curl http://localhost:8006/health
echo "RAG Engine started with PID: $RAG_PID"
```

**Agent Engine**:

```bash
cd ../agent-engine
uvicorn main:app --host 0.0.0.0 --port 8001 &
AGENT_PID=$!
sleep 5
curl http://localhost:8001/health
echo "Agent Engine started with PID: $AGENT_PID"
```

**Voice Engine**:

```bash
cd ../voice-engine
uvicorn main:app --host 0.0.0.0 --port 8002 &
VOICE_PID=$!
sleep 5
curl http://localhost:8002/health
echo "Voice Engine started with PID: $VOICE_PID"
```

**Multimodal Engine**:

```bash
cd ../multimodal-engine
uvicorn main:app --host 0.0.0.0 --port 8003 &
MULTIMODAL_PID=$!
sleep 5
curl http://localhost:8003/health
echo "Multimodal Engine started with PID: $MULTIMODAL_PID"
```

**Model Adapter**:

```bash
cd ../model-adapter
uvicorn main:app --host 0.0.0.0 --port 8005 &
ADAPTER_PID=$!
sleep 5
curl http://localhost:8005/health
echo "Model Adapter started with PID: $ADAPTER_PID"
```

##### 5. 创建启动脚本

```bash
cat > scripts/start-all-services.sh << 'EOF'
#!/bin/bash

set -e

echo "Starting all VoiceHelper services..."

# 启动 Go 服务
echo "Starting Go services..."
cd cmd/identity-service && go run . &
cd ../conversation-service && go run . &
cd ../knowledge-service && go run . &
cd ../ai-orchestrator && go run . &
cd ../model-router && go run . &
cd ../notification-service && go run . &
cd ../analytics-service && go run . &

# 等待 Go 服务启动
sleep 10

# 启动 Python 服务
echo "Starting Python AI services..."
cd ../../algo/indexing-service && uvicorn main:app --host 0.0.0.0 --port 8011 &
cd ../retrieval-service && uvicorn main:app --host 0.0.0.0 --port 8012 &
cd ../rag-engine && uvicorn main:app --host 0.0.0.0 --port 8006 &
cd ../agent-engine && uvicorn main:app --host 0.0.0.0 --port 8001 &
cd ../voice-engine && uvicorn main:app --host 0.0.0.0 --port 8002 &
cd ../multimodal-engine && uvicorn main:app --host 0.0.0.0 --port 8003 &
cd ../model-adapter && uvicorn main:app --host 0.0.0.0 --port 8005 &

echo "All services started! Check health with: ./scripts/check-health.sh"
EOF

chmod +x scripts/start-all-services.sh
```

##### 6. 创建健康检查脚本

```bash
cat > scripts/check-health.sh << 'EOF'
#!/bin/bash

echo "Checking service health..."

services=(
  "Identity:8081"
  "Conversation:8082"
  "Knowledge:8083"
  "Orchestrator:8084"
  "ModelRouter:8085"
  "Notification:8086"
  "Analytics:8087"
  "Indexing:8011"
  "Retrieval:8012"
  "RAG:8006"
  "Agent:8001"
  "Voice:8002"
  "Multimodal:8003"
  "ModelAdapter:8005"
)

for service in "${services[@]}"; do
  name=$(echo $service | cut -d: -f1)
  port=$(echo $service | cut -d: -f2)

  if curl -s http://localhost:${port}/health > /dev/null; then
    echo "✅ ${name} (${port}): OK"
  else
    echo "❌ ${name} (${port}): FAILED"
  fi
done
EOF

chmod +x scripts/check-health.sh
```

##### 7. 运行验证

```bash
# 启动所有服务
./scripts/start-all-services.sh

# 等待所有服务启动
sleep 30

# 健康检查
./scripts/check-health.sh
```

##### 8. 创建启动文档

````bash
cat > docs/development/service-startup-guide.md << 'EOF'
# 服务启动指南

## 前置条件

1. 安装依赖:
   - Go 1.21+
   - Python 3.11+
   - Docker & Docker Compose

2. 生成代码:
   ```bash
   make wire-gen
   make proto-gen
````

## 启动步骤

### 1. 启动基础设施

```bash
make dev-up
# 或
docker-compose up -d
```

验证:

```bash
docker-compose ps
```

### 2. 启动所有服务

```bash
./scripts/start-all-services.sh
```

### 3. 健康检查

```bash
./scripts/check-health.sh
```

## 服务端口

### Go 微服务

| 服务                 | HTTP 端口 | gRPC 端口 |
| -------------------- | --------- | --------- |
| Identity Service     | 8081      | 9081      |
| Conversation Service | 8082      | 9082      |
| Knowledge Service    | 8083      | 9083      |
| AI Orchestrator      | 8084      | 9084      |
| Model Router         | 8085      | 9085      |
| Notification Service | 8086      | 9086      |
| Analytics Service    | 8087      | 9087      |

### Python AI 服务

| 服务              | HTTP 端口 |
| ----------------- | --------- |
| Agent Engine      | 8001      |
| Voice Engine      | 8002      |
| Multimodal Engine | 8003      |
| Model Adapter     | 8005      |
| RAG Engine        | 8006      |
| Indexing Service  | 8011      |
| Retrieval Service | 8012      |

### 基础设施

| 服务       | 端口       | 访问                   |
| ---------- | ---------- | ---------------------- |
| PostgreSQL | 5432       | -                      |
| Redis      | 6379       | -                      |
| Kafka      | 9092       | -                      |
| Milvus     | 19530      | -                      |
| Neo4j      | 7474, 7687 | http://localhost:7474  |
| ClickHouse | 8123, 9000 | -                      |
| MinIO      | 9000, 9001 | http://localhost:9001  |
| Prometheus | 9090       | http://localhost:9090  |
| Grafana    | 3000       | http://localhost:3000  |
| Jaeger     | 16686      | http://localhost:16686 |

## 停止服务

```bash
# 停止所有 Go/Python 进程
pkill -f "go run"
pkill -f "uvicorn"

# 停止基础设施
make dev-down
# 或
docker-compose down
```

## 故障排查

### 服务启动失败

1. 检查日志
2. 确认端口未被占用: `lsof -i :8081`
3. 确认配置文件正确
4. 检查依赖服务状态

### 健康检查失败

1. 查看服务日志
2. 检查数据库连接
3. 确认所有依赖服务运行中
   EOF

````

**验收标准**:
- [ ] 基础设施所有容器运行正常
- [ ] 所有 14 个服务健康检查通过
- [ ] 启动脚本可用: `scripts/start-all-services.sh`
- [ ] 健康检查脚本可用: `scripts/check-health.sh`
- [ ] 启动文档完成: `docs/development/service-startup-guide.md`

---

## Day 4-5: MinIO 集成

### Task 1.4: MinIO 集成 Knowledge Service (P1)

**目标**: 实现文件上传/下载到 MinIO

#### 步骤

##### 1. 实现 MinIO 客户端

```bash
cd cmd/knowledge-service/internal/infra
cat > minio_client.go << 'EOF'
package infra

import (
	"context"
	"fmt"
	"io"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type MinIOClient struct {
	client     *minio.Client
	bucketName string
}

type MinIOConfig struct {
	Endpoint        string
	AccessKeyID     string
	SecretAccessKey string
	UseSSL          bool
	BucketName      string
}

func NewMinIOClient(config *MinIOConfig) (*MinIOClient, error) {
	// 初始化 MinIO 客户端
	client, err := minio.New(config.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(config.AccessKeyID, config.SecretAccessKey, ""),
		Secure: config.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create minio client: %w", err)
	}

	// 确保 bucket 存在
	ctx := context.Background()
	exists, err := client.BucketExists(ctx, config.BucketName)
	if err != nil {
		return nil, fmt.Errorf("failed to check bucket existence: %w", err)
	}
	if !exists {
		err = client.MakeBucket(ctx, config.BucketName, minio.MakeBucketOptions{})
		if err != nil {
			return nil, fmt.Errorf("failed to create bucket: %w", err)
		}
	}

	return &MinIOClient{
		client:     client,
		bucketName: config.BucketName,
	}, nil
}

// UploadFile 上传文件
func (m *MinIOClient) UploadFile(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) error {
	_, err := m.client.PutObject(ctx, m.bucketName, objectName, reader, size, minio.PutObjectOptions{
		ContentType: contentType,
	})
	if err != nil {
		return fmt.Errorf("failed to upload file: %w", err)
	}
	return nil
}

// DownloadFile 下载文件
func (m *MinIOClient) DownloadFile(ctx context.Context, objectName string) (*minio.Object, error) {
	object, err := m.client.GetObject(ctx, m.bucketName, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to download file: %w", err)
	}
	return object, nil
}

// GetPresignedURL 生成预签名 URL
func (m *MinIOClient) GetPresignedURL(ctx context.Context, objectName string, expires time.Duration) (string, error) {
	url, err := m.client.PresignedGetObject(ctx, m.bucketName, objectName, expires, nil)
	if err != nil {
		return "", fmt.Errorf("failed to generate presigned url: %w", err)
	}
	return url.String(), nil
}

// DeleteFile 删除文件
func (m *MinIOClient) DeleteFile(ctx context.Context, objectName string) error {
	err := m.client.RemoveObject(ctx, m.bucketName, objectName, minio.RemoveObjectOptions{})
	if err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}
	return nil
}

// FileExists 检查文件是否存在
func (m *MinIOClient) FileExists(ctx context.Context, objectName string) (bool, error) {
	_, err := m.client.StatObject(ctx, m.bucketName, objectName, minio.StatObjectOptions{})
	if err != nil {
		errResponse := minio.ToErrorResponse(err)
		if errResponse.Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}
EOF
````

##### 2. 添加文件上传 API

```bash
cd ../service
cat > document_upload.go << 'EOF'
package service

import (
	"context"
	"fmt"
	"io"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"voiceassistant/cmd/knowledge-service/internal/biz"
	"voiceassistant/cmd/knowledge-service/internal/infra"
)

type DocumentUploadService struct {
	minioClient *infra.MinIOClient
	docUsecase  *biz.DocumentUsecase
}

func NewDocumentUploadService(
	minioClient *infra.MinIOClient,
	docUsecase *biz.DocumentUsecase,
) *DocumentUploadService {
	return &DocumentUploadService{
		minioClient: minioClient,
		docUsecase:  docUsecase,
	}
}

func (s *DocumentUploadService) UploadDocument(
	ctx context.Context,
	filename string,
	fileReader io.Reader,
	fileSize int64,
	contentType string,
	knowledgeBaseID string,
	userID string,
) (*biz.Document, error) {
	// 生成唯一文件名
	objectName := fmt.Sprintf("%s/%s-%s", knowledgeBaseID, uuid.New().String(), filepath.Base(filename))

	// 上传到 MinIO
	err := s.minioClient.UploadFile(ctx, objectName, fileReader, fileSize, contentType)
	if err != nil {
		return nil, fmt.Errorf("failed to upload to minio: %w", err)
	}

	// 创建文档记录
	doc := &biz.Document{
		ID:              uuid.New().String(),
		KnowledgeBaseID: knowledgeBaseID,
		Name:            filename,
		ContentType:     contentType,
		Size:            fileSize,
		StoragePath:     objectName,
		UploadedBy:      userID,
		Status:          "pending",
		CreatedAt:       time.Now(),
	}

	// 保存到数据库
	err = s.docUsecase.CreateDocument(ctx, doc)
	if err != nil {
		// 回滚: 删除 MinIO 文件
		_ = s.minioClient.DeleteFile(ctx, objectName)
		return nil, fmt.Errorf("failed to create document record: %w", err)
	}

	return doc, nil
}

func (s *DocumentUploadService) GetDownloadURL(ctx context.Context, documentID string) (string, error) {
	// 获取文档记录
	doc, err := s.docUsecase.GetDocumentByID(ctx, documentID)
	if err != nil {
		return "", fmt.Errorf("document not found: %w", err)
	}

	// 生成预签名 URL (有效期 1 小时)
	url, err := s.minioClient.GetPresignedURL(ctx, doc.StoragePath, time.Hour)
	if err != nil {
		return "", fmt.Errorf("failed to generate download url: %w", err)
	}

	return url, nil
}
EOF
```

##### 3. 添加 HTTP 接口

```bash
cd ../server
# 在 http.go 中添加上传接口
# (具体实现根据现有 HTTP 服务器框架)
```

##### 4. 测试

```bash
# 测试上传
curl -X POST http://localhost:8083/api/v1/documents/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.pdf" \
  -F "knowledge_base_id=kb_123" \
  -F "user_id=user_456"

# 应该返回:
# {
#   "id": "doc_xxx",
#   "name": "test.pdf",
#   "size": 12345,
#   "status": "pending"
# }

# 测试下载
curl http://localhost:8083/api/v1/documents/doc_xxx/download

# 应该返回预签名 URL
```

**验收标准**:

- [ ] `internal/infra/minio_client.go` 实现完成
- [ ] `internal/service/document_upload.go` 实现完成
- [ ] HTTP 接口实现完成
- [ ] 单元测试通过
- [ ] curl 上传/下载测试成功
- [ ] 文件在 MinIO 可见: http://localhost:9001

---

## 验收与交付

### Week 1 整体验收标准

- [ ] **Task 1.1**: 所有 7 个 Go 服务 `wire_gen.go` 生成
- [ ] **Task 1.2**: Go 和 Python proto 代码生成
- [ ] **Task 1.3**: 所有 14 个服务健康检查通过
- [ ] **Task 1.4**: MinIO 文件上传/下载可用

### 交付物

1. **代码**:

   - `cmd/*/wire_gen.go` (7 个文件)
   - `api/proto/*/v1/*.pb.go` (Go proto)
   - `algo/*/app/protos/*_pb2.py` (Python proto)
   - `cmd/knowledge-service/internal/infra/minio_client.go`

2. **脚本**:

   - `scripts/proto-gen.sh`
   - `scripts/start-all-services.sh`
   - `scripts/check-health.sh`

3. **文档**:

   - `docs/development/service-startup-guide.md`
   - Week 1 完成报告: `docs/reports/week1-completion-report.md`

4. **Makefile 任务**:
   - `make wire-gen`
   - `make proto-gen`
   - `make build-all`

---

## 故障排查

### Wire 生成失败

**症状**: `wire: no provider found for ...`

**解决**:

1. 检查 `wire.go` 中的 provider 列表
2. 确保所有依赖的构造函数存在
3. 检查 import 路径是否正确

### Proto 生成失败

**症状**: `protoc: command not found`

**解决**:

```bash
# macOS
brew install protobuf

# Linux
sudo apt-get install -y protobuf-compiler
```

### 服务启动失败

**症状**: 端口被占用

**解决**:

```bash
# 查找占用进程
lsof -i :8081

# 杀死进程
kill -9 <PID>
```

### MinIO 连接失败

**症状**: `dial tcp: connection refused`

**解决**:

1. 确认 MinIO 容器运行: `docker ps | grep minio`
2. 检查端口映射: `docker-compose ps`
3. 检查配置: `endpoint=localhost:9000`, not `minio:9000`

---

## 下一步 (Week 2)

Week 1 完成后，进入 **Week 2: Kafka 事件系统集成**

关键任务:

- Knowledge Service Kafka Producer
- Conversation Service Kafka Producer
- Indexing Service Kafka Consumer

---

**更新日期**: 2025-10-27
**负责人**: Tech Lead
**审查**: 每日站会

---

**💡 记住**: Week 1 是关键周，所有 P0 阻塞项必须解决！

**Let's get started! 🚀**
