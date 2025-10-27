#!/bin/bash

# Start Monitoring Stack
# This script starts Prometheus, Grafana, Jaeger, and related monitoring services

set -e

echo "🚀 Starting VoiceAssistant Monitoring Stack..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed."
    exit 1
fi

# Start monitoring services
echo "📊 Starting monitoring services..."
docker-compose -f docker-compose.monitoring.yml up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "🔍 Checking service health..."

# Check Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is running"
else
    echo "⚠️  Prometheus may not be ready yet"
fi

# Check Grafana
if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is running"
else
    echo "⚠️  Grafana may not be ready yet"
fi

# Check Jaeger
if curl -s http://localhost:16686 > /dev/null 2>&1; then
    echo "✅ Jaeger is running"
else
    echo "⚠️  Jaeger may not be ready yet"
fi

echo ""
echo "✅ Monitoring stack started successfully!"
echo ""
echo "📊 Access URLs:"
echo "  Prometheus:   http://localhost:9090"
echo "  Grafana:      http://localhost:3001 (admin/admin)"
echo "  Jaeger:       http://localhost:16686"
echo "  AlertManager: http://localhost:9093"
echo ""
echo "📝 Next steps:"
echo "  1. Access Grafana and explore dashboards"
echo "  2. Configure AlertManager notifications"
echo "  3. Start your services to see metrics"
echo ""
echo "🛑 To stop: ./scripts/stop-monitoring.sh"

