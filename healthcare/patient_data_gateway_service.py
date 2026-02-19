# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""Patient Data Gateway Service

Simulates FHIR R4 / HL7 v2 gateway interactions for development and demo purposes.
Provides clinical data exchange, patient consent management, and HIPAA-compliant
data routing with configurable latency and error injection for chaos testing.
"""

import os
import json
import uuid
import time
import random
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PatientDataGateway")

app = Flask(__name__)

# Simulated state
processed_requests = []
consent_records = []
injected_latency_ms = 0
injected_error_rate = 0.0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "patient-data-gateway",
        "version": "1.0.0",
        "fhir_version": "R4",
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "total_requests": len(processed_requests),
        "avg_latency_ms": 28.4,
        "error_rate": injected_error_rate,
        "consent_records": len(consent_records),
        "supported_formats": ["FHIR-R4", "HL7v2", "CDA-R2", "C-CDA"],
    })

@app.route('/api/v1/fhir/query', methods=['POST'])
def query_patient_data():
    """Query patient data through the FHIR gateway (HIPAA-audited)."""
    start_time = time.time()

    # Simulate injected latency
    if injected_latency_ms > 0:
        time.sleep(injected_latency_ms / 1000.0)

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    # Simulate injected errors
    if random.random() < injected_error_rate:
        logger.error(f"[SIMULATED] FHIR gateway error for patient={data.get('patient_id')}")
        return jsonify({
            "request_id": str(uuid.uuid4()),
            "status": "failed",
            "error_code": "GATEWAY_ERROR",
            "error_message": "Simulated FHIR gateway failure",
        }), 502

    # HIPAA audit log
    logger.info(
        f"[HIPAA-AUDIT] FHIR query: patient={data.get('patient_id', 'unknown')} "
        f"resource={data.get('resource_type', 'Patient')} user=system action=query"
    )

    result = {
        "request_id": str(uuid.uuid4()),
        "patient_id": data.get("patient_id", "unknown"),
        "resource_type": data.get("resource_type", "Patient"),
        "status": "completed",
        "result_count": random.randint(1, 15),
        "format": data.get("format", "FHIR-R4"),
        "timestamp": time.time(),
    }

    processing_ms = (time.time() - start_time) * 1000
    result["processing_ms"] = round(processing_ms, 2)

    processed_requests.append(result)
    logger.info(f"FHIR query processed: {result['request_id']} patient={result['patient_id']}")

    return jsonify(result), 200

@app.route('/api/v1/consent/register', methods=['POST'])
def register_consent():
    """Register patient data sharing consent (HIPAA §164.508)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    consent = {
        "consent_id": str(uuid.uuid4()),
        "patient_id": data.get("patient_id", "unknown"),
        "scope": data.get("scope", "treatment"),
        "granted_to": data.get("granted_to", "primary-care-provider"),
        "data_categories": data.get("data_categories", ["demographics", "vitals"]),
        "valid_from": data.get("valid_from", time.time()),
        "valid_until": data.get("valid_until", time.time() + 365 * 24 * 3600),
        "status": "active",
        "timestamp": time.time(),
    }

    consent_records.append(consent)

    logger.info(
        f"[HIPAA-AUDIT] Consent registered: patient={consent['patient_id']} "
        f"scope={consent['scope']} granted_to={consent['granted_to']}"
    )

    return jsonify(consent), 201

@app.route('/api/v1/consent/verify', methods=['POST'])
def verify_consent():
    """Verify patient consent before data access (HIPAA §164.508)."""
    data = request.get_json()
    patient_id = data.get("patient_id", "unknown")
    scope = data.get("scope", "treatment")

    matching = [
        c for c in consent_records
        if c["patient_id"] == patient_id
        and c["scope"] == scope
        and c["status"] == "active"
    ]

    has_consent = len(matching) > 0

    logger.info(
        f"[HIPAA-AUDIT] Consent verification: patient={patient_id} "
        f"scope={scope} result={'granted' if has_consent else 'denied'}"
    )

    return jsonify({
        "patient_id": patient_id,
        "scope": scope,
        "consent_granted": has_consent,
        "matching_consents": len(matching),
    })

@app.route('/api/v1/exchange/status', methods=['GET'])
def exchange_status():
    """Get current clinical data exchange status."""
    return jsonify({
        "exchange_id": str(uuid.uuid4()),
        "status": "active",
        "connected_systems": ["epic", "cerner", "meditech", "allscripts"],
        "pending_exchanges": random.randint(0, 25),
        "completed_today": len(processed_requests),
    })

@app.route('/ops/chaos/latency', methods=['POST'])
def inject_latency():
    """Chaos endpoint: inject gateway processing latency."""
    global injected_latency_ms
    injected_latency_ms = request.get_json().get("delay_ms", 500)
    logger.warning(f"[CHAOS] Patient Data Gateway latency set to {injected_latency_ms}ms")
    return jsonify({"chaos": "latency_injected", "delay_ms": injected_latency_ms})

@app.route('/ops/chaos/error', methods=['POST'])
def inject_errors():
    """Chaos endpoint: inject gateway errors."""
    global injected_error_rate
    injected_error_rate = request.get_json().get("error_rate", 0.1)
    logger.warning(f"[CHAOS] Patient Data Gateway error rate set to {injected_error_rate*100}%")
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
    port = int(os.environ.get('PORT', 8095))
    logger.info(f"Patient Data Gateway starting on port {port}")
    app.run(host='0.0.0.0', port=port)
