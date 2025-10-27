# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /build

# 安装构建依赖
RUN apk add --no-cache git make

# 复制依赖文件
COPY go.mod go.sum ./
RUN go mod download

# 复制整个项目
COPY . .

# 编译服务
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.Version=$(git describe --tags --always)" \
    -o /build/bin/ai-orchestrator \
    ./cmd/ai-orchestrator

# Runtime stage
FROM alpine:latest

# 安装运行时依赖
RUN apk --no-cache add ca-certificates tzdata curl && \
    addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser

WORKDIR /app

# 从构建阶段复制二进制文件
COPY --from=builder /build/bin/ai-orchestrator /app/ai-orchestrator

# 复制配置文件（如果存在）
COPY --from=builder /build/configs/app/ai-orchestrator.yaml /etc/voiceassistant/ai-orchestrator.yaml

# 切换到非root用户
USER appuser

# 暴露端口
# 8000: HTTP端口
# 9000: gRPC端口
EXPOSE 8000 9000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
ENTRYPOINT ["/app/ai-orchestrator"]
CMD ["-conf", "/etc/voiceassistant/ai-orchestrator.yaml"]
