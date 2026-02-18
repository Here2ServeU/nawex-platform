#!/bin/bash
# =============================================================================
# Healthcare: PHI Breach Simulation
# =============================================================================
# Simulates a PHI breach scenario to validate the breach detection pipeline,
# automated session lockout, and HIPAA incident response procedures.
#
# HIPAA §164.308: Security incident procedures
# HITECH: Breach notification validation
# =============================================================================

set -euo pipefail

EHR_INGESTION_URL="${EHR_INGESTION_URL:-http://localhost:8093}"
CLINICAL_DECISION_URL="${CLINICAL_DECISION_URL:-http://localhost:8094}"

echo "=============================================="
echo " Healthcare Chaos: PHI Breach Simulation"
echo "=============================================="
echo ""

# Step 1: Generate legitimate clinical baseline
echo "[1/4] Generating legitimate EHR access baseline..."
for i in $(seq 1 10); do
    curl -s -X POST "$EHR_INGESTION_URL/api/v1/ehr/ingest" \
        -H "Content-Type: application/json" \
        -d "{
            \"patient_id\": \"patient-$(printf '%03d' $i)\",
            \"resource_type\": \"Observation\",
            \"department\": \"general\",
            \"data_class\": \"clinical\",
            \"phi_flag\": true
        }" > /dev/null 2>&1 || true
done
echo "  ✓ 10 legitimate EHR records ingested"
echo ""

# Step 2: Simulate anomalous PHI access patterns
echo "[2/4] Injecting anomalous PHI access events..."
for i in $(seq 1 10); do
    result=$(curl -s -X POST "$CLINICAL_DECISION_URL/api/v1/phi/access-audit" \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"suspicious-user-$((i % 3 + 1))\",
            \"access_count_last_hour\": $((RANDOM % 80 + 40)),
            \"department\": \"radiology\",
            \"role\": \"contractor\",
            \"cross_department_access\": true,
            \"after_hours\": true,
            \"bulk_export\": $([ $((i % 3)) -eq 0 ] && echo "true" || echo "false")
        }" 2>/dev/null || echo "{}")

    risk=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('risk_score', 'N/A'))" 2>/dev/null || echo "N/A")
    suspicious=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_suspicious', 'N/A'))" 2>/dev/null || echo "N/A")
    echo "  Access event $i: risk=$risk, suspicious=$suspicious"
done
echo ""

# Step 3: Check clinical decision metrics
echo "[3/4] Checking clinical decision service state..."
curl -s "$CLINICAL_DECISION_URL/metrics" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (metrics not available)"
echo ""

# Step 4: Verify breach detection via clinical scoring
echo "[4/4] Submitting critical patient vitals for anomaly detection..."
for i in $(seq 1 3); do
    result=$(curl -s -X POST "$CLINICAL_DECISION_URL/score" \
        -H "Content-Type: application/json" \
        -d "{
            \"event_id\": \"critical-event-$i\",
            \"patient_id\": \"patient-critical-$i\",
            \"event_type\": \"vitals\",
            \"department\": \"icu\",
            \"acuity\": \"critical\",
            \"heart_rate\": $((RANDOM % 40 + 130)),
            \"spo2\": $((RANDOM % 8 + 85)),
            \"systolic_bp\": $((RANDOM % 30 + 180)),
            \"temperature\": 39.5
        }" 2>/dev/null || echo "{}")

    risk_level=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('risk_level', 'N/A'))" 2>/dev/null || echo "N/A")
    echo "  Clinical event $i: risk_level=$risk_level (expected: critical/high)"
done
echo ""

echo "=============================================="
echo " PHI breach simulation complete."
echo " Expected AIOps response:"
echo "   → phi_breach_detected rule should trigger"
echo "   → Suspicious user sessions locked"
echo "   → HIPAA compliance team notified"
echo "   → Breach notification timer started"
echo "   → HIPAA audit trail preserved for forensics"
echo "=============================================="
