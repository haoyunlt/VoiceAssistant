module voiceassistant

go 1.21

require (
	github.com/go-kratos/kratos/v2 v2.7.2
	github.com/go-redis/redis/v8 v8.11.5
	github.com/golang-jwt/jwt/v5 v5.2.0
	github.com/google/uuid v1.5.0
	github.com/google/wire v0.5.0
	github.com/lib/pq v1.10.9
	go.opentelemetry.io/otel v1.21.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.21.0
	go.opentelemetry.io/otel/sdk v1.21.0
	go.uber.org/automaxprocs v1.5.3
	golang.org/x/crypto v0.17.0
	google.golang.org/grpc v1.60.1
	google.golang.org/protobuf v1.31.0
	github.com/prometheus/client_golang v1.17.0
	gorm.io/driver/postgres v1.5.4
	gorm.io/gorm v1.25.5
)
