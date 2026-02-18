"""Payment Gateway Simulator Service

Simulates payment processor interactions for development and demo purposes.
Supports configurable latency, error injection, and settlement batch processing.
"""

import os
import json
import uuid
import time
import random
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaymentGateway")

app = Flask(__name__)

# Simulated state
processed_payments = []
settlement_batches = []
injected_latency_ms = 0
injected_error_rate = 0.0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "payment-gateway",
        "version": "1.0.0",
        "processor": "simulated",
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "total_processed": len(processed_payments),
        "avg_latency_ms": 35.8,
        "error_rate": injected_error_rate,
        "settlement_batches": len(settlement_batches),
        "currencies_supported": ["USD", "EUR", "GBP", "JPY", "CHF", "CAD"],
    })

@app.route('/api/v1/process', methods=['POST'])
def process_payment():
    """Process a payment through the simulated gateway."""
    start_time = time.time()
    
    # Simulate injected latency
    if injected_latency_ms > 0:
        time.sleep(injected_latency_ms / 1000.0)
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400
    
    # Simulate injected errors
    if random.random() < injected_error_rate:
        logger.error(f"[SIMULATED] Payment processing error for amount={data.get('amount')}")
        return jsonify({
            "payment_id": str(uuid.uuid4()),
            "status": "failed",
            "error_code": "GATEWAY_ERROR",
            "error_message": "Simulated payment processing failure",
        }), 502
    
    payment = {
        "payment_id": str(uuid.uuid4()),
        "transaction_id": data.get("transaction_id", str(uuid.uuid4())),
        "amount": data.get("amount", 0),
        "currency": data.get("currency", "USD"),
        "status": "settled",
        "processor_response_code": "00",
        "processor_response_message": "Approved",
        "timestamp": time.time(),
    }
    
    processing_ms = (time.time() - start_time) * 1000
    payment["processing_ms"] = round(processing_ms, 2)
    
    processed_payments.append(payment)
    logger.info(f"Payment processed: {payment['payment_id']} amount={payment['amount']} {payment['currency']}")
    
    return jsonify(payment), 201

@app.route('/api/v1/settlement/trigger', methods=['POST'])
def trigger_settlement():
    """Trigger a settlement batch."""
    batch = {
        "batch_id": str(uuid.uuid4()),
        "status": "processing",
        "transactions_count": len(processed_payments),
        "total_amount": sum(p['amount'] for p in processed_payments),
        "currency": "USD",
        "started_at": time.time(),
    }
    settlement_batches.append(batch)
    logger.info(f"Settlement batch triggered: {batch['batch_id']} ({batch['transactions_count']} txns)")
    return jsonify(batch), 201

@app.route('/api/v1/settlement/batches', methods=['GET'])
def list_settlement_batches():
    """List settlement batches."""
    return jsonify({"batches": settlement_batches, "total": len(settlement_batches)})

@app.route('/ops/chaos/latency', methods=['POST'])
def inject_latency():
    """Chaos endpoint: inject gateway processing latency."""
    global injected_latency_ms
    injected_latency_ms = request.get_json().get("delay_ms", 500)
    logger.warning(f"[CHAOS] Gateway latency set to {injected_latency_ms}ms")
    return jsonify({"chaos": "latency_injected", "delay_ms": injected_latency_ms})

@app.route('/ops/chaos/error', methods=['POST'])
def inject_errors():
    """Chaos endpoint: inject gateway errors."""
    global injected_error_rate
    injected_error_rate = request.get_json().get("error_rate", 0.1)
    logger.warning(f"[CHAOS] Gateway error rate set to {injected_error_rate*100}%")
    return jsonify({"chaos": "errors_injected", "error_rate": injected_error_rate})

@app.route('/ops/reset', methods=['POST'])
def reset():
    """Reset all chaos injections."""
    global injected_latency_ms, injected_error_rate
    injected_latency_ms = 0
    injected_error_rate = 0.0
    logger.info("[RESET] All chaos injections cleared")
    return jsonify({"status": "reset", "latency_ms": 0, "error_rate": 0.0})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8092))
    logger.info(f"Payment Gateway Simulator starting on port {port}")
    app.run(host='0.0.0.0', port=port)
