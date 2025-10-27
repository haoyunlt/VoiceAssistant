# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git make

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o ai-orchestrator .

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

COPY --from=builder /app/ai-orchestrator .
COPY --from=builder /app/../../configs/app/ai-orchestrator.yaml /etc/voiceassistant/ai-orchestrator.yaml

EXPOSE 9003 8003

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8003/health || exit 1

CMD ["./ai-orchestrator"]
