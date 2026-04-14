#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
# =============================================================================
# Start Healthcare Services
# =============================================================================
# Brings up the healthcare vertical: EHR Ingestion, Clinical Decision Support,
# Patient Data Gateway, and supporting services.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=============================================="
echo " NRP: Healthcare Services"
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
    echo " Waiting for Kafka to be healthy..."
    sleep 10
    echo " Kafka started"
else
    echo "[1/3] Kafka already running "
fi
echo ""

# Start Healthcare services
echo "[2/3] Starting Healthcare services..."
cd "$ROOT_DIR"
docker compose up -d healthcare-redis ehr-ingestion clinical-decision patient-data-gateway healthcare-watchdog
echo " All healthcare services started"
echo ""

# Wait for services to be ready
echo "[3/3] Waiting for services to initialize..."
sleep 5

# Health checks
echo ""
echo "Service Health:"
echo "───────────────"

for svc_info in "EHR Ingestion|http://localhost:8093/health" \
                "Clinical Decision|http://localhost:8094/health" \
                "Patient Data Gateway|http://localhost:8095/health"; do
    IFS='|' read -r name url <<< "$svc_info"
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo " $name: healthy"
    else
        echo " $name: starting (status=$status)"
    fi
done

echo ""
echo "=============================================="
echo " Healthcare services are running!"
echo ""
echo " Endpoints:"
echo " EHR Ingestion: http://localhost:8093"
echo " Clinical Decision: http://localhost:8094"
echo " Patient Data Gateway: http://localhost:8095"
echo " Healthcare Redis: localhost:6381"
echo ""
echo " Try:"
echo " curl http://localhost:8094/score -X POST \\"
echo " -H 'Content-Type: application/json' \\"
echo " -d '{\"patient_id\": \"P001\", \"heart_rate\": 110, \"spo2\": 93, \"department\": \"icu\"}'"
echo ""
echo " Chaos:"
echo " sre/chaos/ehr-gateway-failure.sh"
echo " sre/chaos/phi-breach-simulation.sh"
echo "=============================================="
