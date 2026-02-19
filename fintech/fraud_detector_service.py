# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""Fraud Detector Service

Real-time ML-based fraud scoring microservice for the Express-Reliability Fintech vertical.
Scores transactions using the detect_fraud pipeline and returns fraud probability.
"""

import os
import json
import time
import logging
import random
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FraudDetector")

app = Flask(__name__)

# Simulated model state
model_version = "fraud_detector_v1"
scored_transactions = 0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "fraud-detector",
        "model_version": model_version,
        "version": "1.0.0",
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "total_scored": scored_transactions,
        "avg_scoring_ms": 12.5,
        "model_version": model_version,
        "precision": 0.956,
        "recall": 0.923,
        "false_positive_rate": 0.0008,
    })

@app.route('/score', methods=['POST'])
def score_transaction():
    """Score a transaction for fraud probability."""
    global scored_transactions
    start_time = time.time()
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400
    
    # Simulate ML-based fraud scoring
    # In production, this calls detect_fraud.calculate_fraud_score()
    amount = data.get("amount", 0)
    channel = data.get("channel", "online")
    country = data.get("country_code", "US")
    mcc = str(data.get("merchant_category_code", "0000"))
    
    # Base score from transaction characteristics
    base_score = 0.05
    
    # Amount risk
    if amount > 5000:
        base_score += 0.15
    elif amount > 1000:
        base_score += 0.05
    
    # Channel risk
    channel_risk = {"card_not_present": 0.15, "online": 0.10, "mobile": 0.05, "atm": 0.03, "pos": 0.01}
    base_score += channel_risk.get(channel, 0.05)
    
    # Geographic risk
    high_risk = {"NG", "RU", "CN", "BR", "ID", "VN", "PH"}
    if country in high_risk:
        base_score += 0.20
    
    # MCC risk
    risky_mcc = {"7995", "5967", "5966", "6051", "4829"}
    if mcc in risky_mcc:
        base_score += 0.15
    
    # Add slight randomness to simulate model variance
    fraud_score = min(base_score + random.uniform(-0.05, 0.05), 1.0)
    fraud_score = max(fraud_score, 0.0)
    
    scoring_ms = (time.time() - start_time) * 1000
    scored_transactions += 1
    
    threshold = float(os.environ.get('FRAUD_THRESHOLD', '0.85'))
    is_fraud = fraud_score > threshold
    
    result = {
        "transaction_id": data.get("transaction_id", "unknown"),
        "fraud_score": round(fraud_score, 4),
        "is_fraud": is_fraud,
        "risk_level": "critical" if fraud_score > 0.85 else "high" if fraud_score > 0.60 else "medium" if fraud_score > 0.30 else "low",
        "model_version": model_version,
        "scoring_ms": round(scoring_ms, 2),
        "signals": {
            "amount_risk": "high" if amount > 5000 else "medium" if amount > 1000 else "low",
            "channel_risk": channel,
            "geo_risk": "high" if country in high_risk else "low",
            "mcc_risk": "high" if mcc in risky_mcc else "low",
        },
    }
    
    if is_fraud:
        logger.warning(f"FRAUD DETECTED: txn={result['transaction_id']} score={fraud_score:.4f}")
    else:
        logger.info(f"Transaction scored: txn={result['transaction_id']} score={fraud_score:.4f}")
    
    return jsonify(result)

@app.route('/model/swap', methods=['POST'])
def swap_model():
    """Hot-swap the fraud detection model (for failover scenarios)."""
    global model_version
    data = request.get_json()
    new_version = data.get("model_version", "fraud_detector_v2")
    old_version = model_version
    model_version = new_version
    logger.info(f"Model hot-swap: {old_version} -> {new_version}")
    return jsonify({"previous": old_version, "current": model_version, "status": "swapped"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8091))
    logger.info(f"Fraud Detector starting on port {port} with model {model_version}")
    app.run(host='0.0.0.0', port=port)
