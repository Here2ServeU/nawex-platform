#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
# =============================================================================
# Generate Fintech Transaction Traffic
# =============================================================================
# Simulates realistic fintech transaction patterns for demo and load testing.
# Includes a mix of legitimate transactions, edge cases, and suspicious activity.
# =============================================================================

set -euo pipefail

TRANSACTION_ENGINE_URL="${TRANSACTION_ENGINE_URL:-http://localhost:8090}"
FRAUD_DETECTOR_URL="${FRAUD_DETECTOR_URL:-http://localhost:8091}"
DURATION=${1:-30}
TPS=${2:-5}

echo "=============================================="
echo " Fintech Traffic Generator"
echo " Duration: ${DURATION}s | Target TPS: ${TPS}"
echo "=============================================="
echo ""

CHANNELS=("online" "pos" "mobile" "atm" "card_not_present")
COUNTRIES=("US" "GB" "DE" "FR" "JP" "CA" "AU" "BR" "NG" "SG")
MCCS=("5411" "5812" "5541" "7011" "5912" "5999" "7995" "6051")
CURRENCIES=("USD" "EUR" "GBP" "JPY" "CHF")

total_txns=0
blocked=0
errors=0
start_time=$(date +%s)

echo "Generating transactions..."
echo ""

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    if [ "$elapsed" -ge "$DURATION" ]; then
        break
    fi

    for _ in $(seq 1 "$TPS"); do
        # Determine transaction profile (90% legit, 10% suspicious)
        if [ $((RANDOM % 10)) -lt 9 ]; then
            # Legitimate transaction
            amount=$((RANDOM % 500 + 5))
            channel="${CHANNELS[$((RANDOM % 3))]}"
            country="${COUNTRIES[$((RANDOM % 7))]}"
            mcc="${MCCS[$((RANDOM % 6))]}"
        else
            # Suspicious transaction
            amount=$((RANDOM % 9000 + 3000))
            channel="card_not_present"
            country="${COUNTRIES[$((RANDOM % ${#COUNTRIES[@]}))]}"
            mcc="${MCCS[$((RANDOM % ${#MCCS[@]}))]}"
        fi

        currency="${CURRENCIES[$((RANDOM % ${#CURRENCIES[@]}))]}"
        account_id="acct-$(printf '%05d' $((RANDOM % 1000)))"

        # Score with fraud detector
        fraud_result=$(curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$FRAUD_DETECTOR_URL/score" \
            -H "Content-Type: application/json" \
            -d "{
                \"transaction_id\": \"txn-${total_txns}\",
                \"amount\": ${amount},
                \"channel\": \"${channel}\",
                \"country_code\": \"${country}\",
                \"merchant_category_code\": \"${mcc}\"
            }" 2>/dev/null || echo "{}")

        fraud_score=$(echo "$fraud_result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('fraud_score', 0))" 2>/dev/null || echo "0")

        # Submit to transaction engine
        txn_result=$(curl -s -X POST -H "X-API-Key: ${GOLDEN_API_KEY:-}" "$TRANSACTION_ENGINE_URL/api/v1/transactions" \
            -H "Content-Type: application/json" \
            -d "{
                \"account_id\": \"${account_id}\",
                \"amount\": ${amount},
                \"currency\": \"${currency}\",
                \"channel\": \"${channel}\",
                \"merchant_category_code\": \"${mcc}\",
                \"fraud_score\": ${fraud_score}
            }" 2>/dev/null || echo "{}")

        status=$(echo "$txn_result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

        total_txns=$((total_txns + 1))
        if [ "$status" = "blocked" ]; then
            blocked=$((blocked + 1))
        elif [ "$status" = "error" ]; then
            errors=$((errors + 1))
        fi
    done

    # Progress update every 5 seconds
    if [ $((elapsed % 5)) -eq 0 ] && [ "$elapsed" -gt 0 ]; then
        echo " [${elapsed}s] Transactions: ${total_txns} | Blocked: ${blocked} | Errors: ${errors}"
    fi

    sleep 1
done

echo ""
echo "=============================================="
echo " Traffic Generation Complete"
echo "───────────────────────────────────────────────"
echo " Total Transactions: ${total_txns}"
echo " Approved: $((total_txns - blocked - errors))"
echo " Blocked (Fraud): ${blocked}"
echo " Errors: ${errors}"
echo " Duration: ${DURATION}s"
echo " Avg TPS: $((total_txns / DURATION))"
echo "=============================================="
