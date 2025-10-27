#!/bin/bash

# Stop Monitoring Stack

set -e

echo "🛑 Stopping VoiceAssistant Monitoring Stack..."

docker-compose -f docker-compose.monitoring.yml down

echo "✅ Monitoring stack stopped"
echo ""
echo "💡 To remove volumes (data will be lost):"
echo "   docker-compose -f docker-compose.monitoring.yml down -v"

