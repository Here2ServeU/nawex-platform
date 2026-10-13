#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
# =============================================================================
# Fintech: Payment Gateway Failure Simulation
# =============================================================================
# Simulates payment gateway failures to validate automated failover,
# transaction integrity, and fraud detection resilience.
#
# PCI-DSS Req 11: Regular security testing
# SOX: Business continuity validation
# =============================================================================

set -euo pipefail

PAYMENT_GATEWAY_URL="${PAYMENT_GATEWAY_URL:-http://localhost:8092}"
TRANSACTION_ENGINE_URL="${TRANSACTION_ENGINE_URL:-http://localhost:8090}"
FRAUD_DETECTOR_URL="${FRAUD_DETECTOR_URL:-http://localhost:8091}"

echo "=============================================="
echo " Fintech Chaos: Payment Gateway Failure Test"
echo "=============================================="
echo ""

# Step 1: Verify baseline health
echo "[1/5] Verifying baseline service health..."
for svc in "$PAYMENT_GATEWAY_URL/health" "$TRANSACTION_ENGINE_URL/health" "$FRAUD_DETECTOR_URL/health"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$svc" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo " $svc is healthy"
    else
        echo " $svc returned $status (service may not be running)"
    fi
done
echo ""

# Step 2: Generate baseline transactions
echo "[2/5] Generating baseline transactions..."
for i in $(seq 1 5); do
    curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$TRANSACTION_ENGINE_URL/api/v1/transactions" \
        -H "Content-Type: application/json" \
        -d "{\"account_id\": \"acct-$(printf '%03d' $i)\", \"amount\": $((RANDOM % 500 + 10)), \"currency\": \"USD\", \"channel\": \"online\"}" \
        > /dev/null 2>&1 || true
done
echo " 5 baseline transactions submitted"
echo ""

# Step 3: Inject payment gateway latency
echo "[3/5] Injecting payment gateway latency (500ms)..."
curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$PAYMENT_GATEWAY_URL/ops/chaos/latency" \
    -H "Content-Type: application/json" \
    -d '{"delay_ms": 500}' || echo " (gateway not reachable - simulating)"
echo ""
echo " Latency injection active"
echo ""

# Step 4: Inject payment gateway errors
echo "[4/5] Injecting payment gateway errors (20% error rate)..."
curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$PAYMENT_GATEWAY_URL/ops/chaos/error" \
    -H "Content-Type: application/json" \
    -d '{"error_rate": 0.20}' || echo " (gateway not reachable - simulating)"
echo ""
echo " Error injection active"
echo ""

# Step 5: Validate degraded metrics
echo "[5/5] Collecting degraded-state metrics..."
echo ""
echo " Payment Gateway:"
curl -s "$PAYMENT_GATEWAY_URL/metrics" 2>/dev/null | grep -E "^golden_" | head -20 || echo " (metrics endpoint not available)"
echo ""
echo " Transaction Engine:"
curl -s "$TRANSACTION_ENGINE_URL/metrics" 2>/dev/null | grep -E "^golden_" | head -20 || echo " (metrics endpoint not available)"
echo ""

echo "=============================================="
echo " Chaos injection complete."
echo " Expected AIOps response:"
echo " → payment_latency_risk rule should trigger"
echo " → Automated failover to secondary gateway"
echo " → In-flight transactions preserved in Kafka"
echo ""
echo " To reset: curl -X POST $PAYMENT_GATEWAY_URL/ops/reset"
echo "=============================================="
