#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
# =============================================================================
# Generate Healthcare EHR Event Traffic
# =============================================================================
# Simulates realistic clinical data patterns for demo and load testing.
# Includes a mix of normal vitals, edge cases, and critical patient alerts.
# =============================================================================

set -euo pipefail

EHR_INGESTION_URL="${EHR_INGESTION_URL:-http://localhost:8093}"
CLINICAL_DECISION_URL="${CLINICAL_DECISION_URL:-http://localhost:8094}"
DURATION=${1:-30}
RPS=${2:-5}

echo "=============================================="
echo " Healthcare Traffic Generator"
echo " Duration: ${DURATION}s | Target RPS: ${RPS}"
echo "=============================================="
echo ""

DEPARTMENTS=("emergency" "icu" "surgery" "general" "cardiology" "oncology" "nicu" "outpatient")
RESOURCE_TYPES=("Observation" "Condition" "Procedure" "MedicationRequest" "DiagnosticReport" "Encounter")
# shellcheck disable=SC2034 # kept for payload variants
ACUITIES=("routine" "standard" "urgent" "critical")

total_events=0
anomalies=0
errors=0
start_time=$(date +%s)

echo "Generating clinical events..."
echo ""

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    if [ "$elapsed" -ge "$DURATION" ]; then
        break
    fi

    for _ in $(seq 1 "$RPS"); do
        patient_id="patient-$(printf '%05d' $((RANDOM % 500)))"
        department="${DEPARTMENTS[$((RANDOM % ${#DEPARTMENTS[@]}))]}"
        resource_type="${RESOURCE_TYPES[$((RANDOM % ${#RESOURCE_TYPES[@]}))]}"

        # Determine vital sign profile (85% normal, 10% borderline, 5% critical)
        roll=$((RANDOM % 100))
        if [ "$roll" -lt 85 ]; then
            # Normal vitals
            heart_rate=$((RANDOM % 30 + 65))
            spo2=$((RANDOM % 4 + 96))
            systolic_bp=$((RANDOM % 20 + 110))
            temperature="37.$((RANDOM % 5))"
            acuity="routine"
        elif [ "$roll" -lt 95 ]; then
            # Borderline vitals
            heart_rate=$((RANDOM % 20 + 95))
            spo2=$((RANDOM % 3 + 93))
            systolic_bp=$((RANDOM % 20 + 135))
            temperature="38.$((RANDOM % 5))"
            acuity="standard"
        else
            # Critical vitals
            heart_rate=$((RANDOM % 30 + 130))
            spo2=$((RANDOM % 6 + 85))
            systolic_bp=$((RANDOM % 30 + 180))
            temperature="39.$((RANDOM % 8))"
            acuity="critical"
        fi

        # Ingest EHR record
        curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$EHR_INGESTION_URL/api/v1/ehr/ingest" \
            -H "Content-Type: application/json" \
            -d "{
                \"patient_id\": \"${patient_id}\",
                \"resource_type\": \"${resource_type}\",
                \"department\": \"${department}\",
                \"phi_flag\": true
            }" > /dev/null 2>&1 || true

        # Score with clinical decision service
        clinical_result=$(curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$CLINICAL_DECISION_URL/score" \
            -H "Content-Type: application/json" \
            -d "{
                \"event_id\": \"evt-${total_events}\",
                \"patient_id\": \"${patient_id}\",
                \"event_type\": \"vitals\",
                \"department\": \"${department}\",
                \"acuity\": \"${acuity}\",
                \"heart_rate\": ${heart_rate},
                \"spo2\": ${spo2},
                \"systolic_bp\": ${systolic_bp},
                \"temperature\": ${temperature}
            }" 2>/dev/null || echo "{}")

        is_anomaly=$(echo "$clinical_result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_anomaly', False))" 2>/dev/null || echo "False")

        total_events=$((total_events + 1))
        if [ "$is_anomaly" = "True" ]; then
            anomalies=$((anomalies + 1))
        fi
    done

    # Progress update every 5 seconds
    if [ $((elapsed % 5)) -eq 0 ] && [ "$elapsed" -gt 0 ]; then
        echo " [${elapsed}s] Events: ${total_events} | Anomalies: ${anomalies} | Errors: ${errors}"
    fi

    sleep 1
done

echo ""
echo "=============================================="
echo " Traffic Generation Complete"
echo "───────────────────────────────────────────────"
echo " Total Events: ${total_events}"
echo " Normal: $((total_events - anomalies - errors))"
echo " Anomalies: ${anomalies}"
echo " Errors: ${errors}"
echo " Duration: ${DURATION}s"
echo " Avg RPS: $((total_events / DURATION))"
echo "=============================================="
