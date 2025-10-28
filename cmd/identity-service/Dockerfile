# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 安装必要的工具
RUN apk add --no-cache git make

# 配置 Go 国内代理
ENV GOPROXY=https://goproxy.cn,direct

# 复制 go.mod 和 go.sum
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码
COPY . .

# 构建二进制文件
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o identity-service .

# Runtime stage
FROM alpine:latest

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

# 从 builder 阶段复制二进制文件
COPY --from=builder /app/identity-service .

# 复制配置文件
COPY --from=builder /app/../../configs/app/identity-service.yaml /etc/voiceassistant/identity-service.yaml

# 暴露端口
EXPOSE 9000 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8000/health || exit 1

# 运行服务
CMD ["./identity-service"]
