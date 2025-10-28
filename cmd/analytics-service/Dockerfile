# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /build

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk add --no-cache git make ca-certificates tzdata

# 配置 Go 国内代理
ENV GOPROXY=https://goproxy.cn,direct

# Copy go module files from root
COPY go.mod go.sum ./
RUN go mod download

# Copy the entire source tree
COPY . .

# Build the service
WORKDIR /build/cmd/analytics-service
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -ldflags="-w -s" -o /analytics-service .

# Runtime stage
FROM alpine:latest

# 配置阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

RUN apk --no-cache add ca-certificates tzdata wget

WORKDIR /app

# Copy binary
COPY --from=builder /analytics-service .

# Copy config file
COPY --from=builder /build/configs/analytics-service.yaml ./configs/

EXPOSE 9006 8006

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8006/health || exit 1

CMD ["./analytics-service", "-config", "./configs/analytics-service.yaml"]
