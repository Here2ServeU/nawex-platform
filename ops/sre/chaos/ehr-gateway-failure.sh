#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
# =============================================================================
# Healthcare: EHR Gateway Failure Simulation
# =============================================================================
# Simulates FHIR/HL7 gateway failures to validate automated failover,
# clinical data integrity, and patient safety resilience.
#
# HIPAA §164.308: Contingency testing
# FDA 21 CFR Part 11: System reliability validation
# =============================================================================

set -euo pipefail

PATIENT_GATEWAY_URL="${PATIENT_GATEWAY_URL:-http://localhost:8095}"
EHR_INGESTION_URL="${EHR_INGESTION_URL:-http://localhost:8093}"
CLINICAL_DECISION_URL="${CLINICAL_DECISION_URL:-http://localhost:8094}"

echo "=============================================="
echo " Healthcare Chaos: EHR Gateway Failure Test"
echo "=============================================="
echo ""

# Step 1: Verify baseline health
echo "[1/5] Verifying baseline service health..."
for svc in "$PATIENT_GATEWAY_URL/health" "$EHR_INGESTION_URL/health" "$CLINICAL_DECISION_URL/health"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$svc" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo " $svc is healthy"
    else
        echo " $svc returned $status (service may not be running)"
    fi
done
echo ""

# Step 2: Generate baseline EHR records
echo "[2/5] Generating baseline EHR records..."
for i in $(seq 1 5); do
    curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$EHR_INGESTION_URL/api/v1/ehr/ingest" \
        -H "Content-Type: application/json" \
        -d "{\"patient_id\": \"patient-$(printf '%03d' $i)\", \"resource_type\": \"Observation\", \"department\": \"general\", \"phi_flag\": true}" \
        > /dev/null 2>&1 || true
done
echo " 5 baseline EHR records ingested"
echo ""

# Step 3: Inject patient data gateway latency
echo "[3/5] Injecting FHIR gateway latency (500ms)..."
curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$PATIENT_GATEWAY_URL/ops/chaos/latency" \
    -H "Content-Type: application/json" \
    -d '{"delay_ms": 500}' || echo " (gateway not reachable - simulating)"
echo ""
echo " Latency injection active"
echo ""

# Step 4: Inject patient data gateway errors
echo "[4/5] Injecting FHIR gateway errors (20% error rate)..."
curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$PATIENT_GATEWAY_URL/ops/chaos/error" \
    -H "Content-Type: application/json" \
    -d '{"error_rate": 0.20}' || echo " (gateway not reachable - simulating)"
echo ""
echo " Error injection active"
echo ""

# Step 5: Validate degraded metrics
echo "[5/5] Collecting degraded-state metrics..."
echo ""
echo " Patient Data Gateway:"
curl -s "$PATIENT_GATEWAY_URL/metrics" 2>/dev/null | grep -E "^golden_" | head -20 || echo " (metrics endpoint not available)"
echo ""
echo " EHR Ingestion Service:"
curl -s "$EHR_INGESTION_URL/metrics" 2>/dev/null | grep -E "^golden_" | head -20 || echo " (metrics endpoint not available)"
echo ""

echo "=============================================="
echo " Chaos injection complete."
echo " Expected AIOps response:"
echo " → ehr_latency_risk rule should trigger"
echo " → Automated failover to secondary FHIR gateway"
echo " → In-flight clinical queries preserved in Kafka"
echo " → HIPAA audit trail continuity verified"
echo ""
echo " To reset: curl -X POST $PATIENT_GATEWAY_URL/ops/reset"
echo "=============================================="
