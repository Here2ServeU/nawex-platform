"""Transaction Engine Service

Core payment processing microservice for the Express-Reliability Fintech vertical.
Receives, validates, and routes financial transactions through the platform.
"""

import os
import json
import uuid
import time
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TransactionEngine")

app = Flask(__name__)

# Simulated transaction store
transactions = []

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "transaction-engine", "version": "1.0.0"})

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "total_transactions": len(transactions),
        "avg_processing_ms": 45.2,
        "error_rate": 0.001,
        "throughput_tps": 1250,
    })

@app.route('/api/v1/transactions', methods=['POST'])
def process_transaction():
    """Process a financial transaction."""
    start_time = time.time()
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400
    
    txn = {
        "id": str(uuid.uuid4()),
        "account_id": data.get("account_id", "unknown"),
        "amount": data.get("amount", 0),
        "currency": data.get("currency", "USD"),
        "merchant": data.get("merchant", "unknown"),
        "merchant_category_code": data.get("merchant_category_code", "0000"),
        "channel": data.get("channel", "online"),
        "status": "pending",
        "timestamp": time.time(),
    }
    
    # Simulate fraud check
    fraud_score = data.get("fraud_score", 0.0)
    if fraud_score > 0.85:
        txn["status"] = "blocked"
        txn["reason"] = "fraud_score_exceeded"
        logger.warning(f"Transaction {txn['id']} BLOCKED: fraud_score={fraud_score}")
    else:
        txn["status"] = "approved"
        logger.info(f"Transaction {txn['id']} APPROVED: amount={txn['amount']} {txn['currency']}")
    
    processing_ms = (time.time() - start_time) * 1000
    txn["processing_ms"] = round(processing_ms, 2)
    
    transactions.append(txn)
    
    return jsonify(txn), 201

@app.route('/api/v1/transactions', methods=['GET'])
def list_transactions():
    """List recent transactions."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({"transactions": transactions[-limit:], "total": len(transactions)})

@app.route('/api/v1/settlement/status', methods=['GET'])
def settlement_status():
    """Get current settlement batch status."""
    return jsonify({
        "batch_id": str(uuid.uuid4()),
        "status": "processing",
        "progress_pct": 67.5,
        "transactions_processed": len(transactions),
        "estimated_completion_minutes": 45,
    })

@app.route('/ops/chaos/latency', methods=['POST'])
def inject_latency():
    """Chaos endpoint: inject payment processing latency."""
    delay_ms = request.get_json().get("delay_ms", 500)
    logger.warning(f"[CHAOS] Injecting {delay_ms}ms latency into transaction processing")
    return jsonify({"chaos": "latency_injected", "delay_ms": delay_ms})

@app.route('/ops/chaos/error', methods=['POST'])
def inject_errors():
    """Chaos endpoint: inject payment processing errors."""
    error_rate = request.get_json().get("error_rate", 0.1)
    logger.warning(f"[CHAOS] Injecting {error_rate*100}% error rate into transaction processing")
    return jsonify({"chaos": "errors_injected", "error_rate": error_rate})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8090))
    logger.info(f"Transaction Engine starting on port {port}")
    app.run(host='0.0.0.0', port=port)
