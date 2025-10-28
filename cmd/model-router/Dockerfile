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

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o model-router .

# Runtime stage
FROM alpine:latest

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

COPY --from=builder /app/model-router .
COPY --from=builder /app/../../configs/app/model-router.yaml /etc/voiceassistant/model-router.yaml

EXPOSE 9004 8004

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8004/health || exit 1

CMD ["./model-router"]
