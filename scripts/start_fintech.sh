#!/bin/bash
# =============================================================================
# Start Fintech Services
# =============================================================================
# Brings up the fintech vertical: Transaction Engine, Fraud Detector,
# Payment Gateway, and supporting services.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=============================================="
echo " Express-Reliability: Fintech Services"
echo "=============================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Start Kafka (shared backbone) if not running
KAFKA_RUNNING=$(docker ps --filter "name=kafka_broker" --format "{{.Names}}" 2>/dev/null || true)
if [ -z "$KAFKA_RUNNING" ]; then
    echo "[1/3] Starting Kafka event backbone..."
    cd "$ROOT_DIR"
    docker compose up -d zookeeper kafka
    echo "  Waiting for Kafka to be healthy..."
    sleep 10
    echo "  ✓ Kafka started"
else
    echo "[1/3] Kafka already running ✓"
fi
echo ""

# Start Fintech services
echo "[2/3] Starting Fintech services..."
cd "$ROOT_DIR"
docker compose up -d fintech-redis transaction-engine fraud-detector payment-gateway fintech-watchdog
echo "  ✓ All fintech services started"
echo ""

# Wait for services to be ready
echo "[3/3] Waiting for services to initialize..."
sleep 5

# Health checks
echo ""
echo "Service Health:"
echo "───────────────"

for svc_info in "Transaction Engine|http://localhost:8090/health" \
                "Fraud Detector|http://localhost:8091/health" \
                "Payment Gateway|http://localhost:8092/health"; do
    IFS='|' read -r name url <<< "$svc_info"
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo "  ✓ $name: healthy"
    else
        echo "  ⏳ $name: starting (status=$status)"
    fi
done

echo ""
echo "=============================================="
echo " Fintech services are running!"
echo ""
echo " Endpoints:"
echo "   Transaction Engine:  http://localhost:8090"
echo "   Fraud Detector:      http://localhost:8091"
echo "   Payment Gateway:     http://localhost:8092"
echo "   Fintech Redis:       localhost:6380"
echo ""
echo " Try:"
echo "   curl http://localhost:8091/score -X POST \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"amount\": 500, \"channel\": \"online\", \"country_code\": \"US\"}'"
echo ""
echo " Chaos:"
echo "   sre/chaos/payment-gateway-failure.sh"
echo "   sre/chaos/transaction-fraud-spike.sh"
echo "=============================================="
