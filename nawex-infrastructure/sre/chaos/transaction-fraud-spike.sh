#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
# =============================================================================
# Fintech: Transaction Fraud Spike Simulation
# =============================================================================
# Simulates a coordinated fraud attack to validate the fraud detection
# pipeline, automated blocking, and incident response procedures.
#
# PCI-DSS Req 11: Security testing
# PSD2 Art. 96: Incident response validation
# =============================================================================

set -euo pipefail

TRANSACTION_ENGINE_URL="${TRANSACTION_ENGINE_URL:-http://localhost:8090}"
FRAUD_DETECTOR_URL="${FRAUD_DETECTOR_URL:-http://localhost:8091}"

echo "=============================================="
echo " Fintech Chaos: Transaction Fraud Spike"
echo "=============================================="
echo ""

# Step 1: Generate legitimate baseline
echo "[1/4] Generating legitimate transaction baseline..."
for i in $(seq 1 10); do
    curl -s -X POST "$FRAUD_DETECTOR_URL/score" \
        -H "Content-Type: application/json" \
        -d "{
            \"transaction_id\": \"legit-$(printf '%03d' $i)\",
            \"amount\": $((RANDOM % 200 + 10)),
            \"channel\": \"pos\",
            \"country_code\": \"US\",
            \"merchant_category_code\": \"5411\"
        }" > /dev/null 2>&1 || true
done
echo " 10 legitimate transactions scored"
echo ""

# Step 2: Inject suspicious high-risk transactions
echo "[2/4] Injecting high-risk fraudulent transactions..."
for i in $(seq 1 10); do
    result=$(curl -s -X POST "$FRAUD_DETECTOR_URL/score" \
        -H "Content-Type: application/json" \
        -d "{
            \"transaction_id\": \"fraud-$(printf '%03d' $i)\",
            \"amount\": $((RANDOM % 9000 + 5000)),
            \"channel\": \"card_not_present\",
            \"country_code\": \"NG\",
            \"merchant_category_code\": \"7995\"
        }" 2>/dev/null || echo "{}")
    
    score=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('fraud_score', 'N/A'))" 2>/dev/null || echo "N/A")
    is_fraud=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_fraud', 'N/A'))" 2>/dev/null || echo "N/A")
    echo " Transaction fraud-$(printf '%03d' $i): score=$score, blocked=$is_fraud"
done
echo ""

# Step 3: Check fraud detector metrics
echo "[3/4] Checking fraud detector state..."
curl -s "$FRAUD_DETECTOR_URL/metrics" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo " (metrics not available)"
echo ""

# Step 4: Submit high-risk transactions to engine
echo "[4/4] Submitting high-fraud-score transactions to engine..."
for i in $(seq 1 3); do
    result=$(curl -s -X POST "$TRANSACTION_ENGINE_URL/api/v1/transactions" \
        -H "Content-Type: application/json" \
        -d "{
            \"account_id\": \"suspicious-acct-$i\",
            \"amount\": $((RANDOM % 9000 + 5000)),
            \"currency\": \"USD\",
            \"channel\": \"card_not_present\",
            \"fraud_score\": 0.95
        }" 2>/dev/null || echo "{}")
    
    status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'N/A'))" 2>/dev/null || echo "N/A")
    echo " Transaction status: $status (expected: blocked)"
done
echo ""

echo "=============================================="
echo " Fraud spike simulation complete."
echo " Expected AIOps response:"
echo " → fraud_spike rule should trigger"
echo " → Suspicious IP ranges blocked"
echo " → fraud-ops-team notified"
echo " → Key rotation initiated via GitOps"
echo "=============================================="
