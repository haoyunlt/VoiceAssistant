# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk add --no-cache git make

# 配置 Go 国内代理
ENV GOPROXY=https://goproxy.cn,direct

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o conversation-service .

# Runtime stage
FROM alpine:latest

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

COPY --from=builder /app/conversation-service .
COPY --from=builder /app/../../configs/app/conversation-service.yaml /etc/voiceassistant/conversation-service.yaml

EXPOSE 9001 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8001/health || exit 1

CMD ["./conversation-service"]
