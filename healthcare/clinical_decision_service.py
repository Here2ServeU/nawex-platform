"""Clinical Decision Support Service

Real-time ML-based clinical anomaly detection and decision support microservice
for the Express-Reliability Healthcare vertical. Monitors patient vitals,
detects PHI access anomalies, and provides clinical risk scoring.
"""

import os
import json
import time
import logging
import random
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ClinicalDecision")

app = Flask(__name__)

# Simulated model state
model_version = "clinical_anomaly_v1"
scored_events = 0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "clinical-decision",
        "model_version": model_version,
        "version": "1.0.0",
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "total_scored": scored_events,
        "avg_scoring_ms": 8.3,
        "model_version": model_version,
        "sensitivity": 0.971,
        "specificity": 0.945,
        "false_alarm_rate": 0.0012,
    })

@app.route('/score', methods=['POST'])
def score_clinical_event():
    """Score a clinical event for anomaly probability."""
    global scored_events
    start_time = time.time()

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    # Simulate ML-based clinical anomaly scoring
    event_type = data.get("event_type", "vitals")
    department = data.get("department", "general")
    patient_acuity = data.get("acuity", "standard")

    # Base risk from event characteristics
    base_score = 0.03

    # Vital sign anomaly detection
    heart_rate = data.get("heart_rate", 75)
    if heart_rate > 120 or heart_rate < 50:
        base_score += 0.25
    elif heart_rate > 100 or heart_rate < 60:
        base_score += 0.10

    spo2 = data.get("spo2", 98)
    if spo2 < 90:
        base_score += 0.30
    elif spo2 < 95:
        base_score += 0.15

    systolic_bp = data.get("systolic_bp", 120)
    if systolic_bp > 180 or systolic_bp < 90:
        base_score += 0.20
    elif systolic_bp > 140 or systolic_bp < 100:
        base_score += 0.08

    temperature = data.get("temperature", 37.0)
    if temperature > 39.0 or temperature < 35.0:
        base_score += 0.20
    elif temperature > 38.0:
        base_score += 0.08

    # Department acuity risk
    dept_risk = {
        "icu": 0.15, "emergency": 0.12, "surgery": 0.10,
        "nicu": 0.15, "oncology": 0.08, "cardiology": 0.08,
        "general": 0.02, "outpatient": 0.01,
    }
    base_score += dept_risk.get(department, 0.03)

    # Patient acuity modifier
    acuity_risk = {"critical": 0.20, "urgent": 0.10, "standard": 0.02, "routine": 0.0}
    base_score += acuity_risk.get(patient_acuity, 0.02)

    # Add slight randomness for model variance
    anomaly_score = min(base_score + random.uniform(-0.03, 0.03), 1.0)
    anomaly_score = max(anomaly_score, 0.0)

    scoring_ms = (time.time() - start_time) * 1000
    scored_events += 1

    threshold = float(os.environ.get('ANOMALY_THRESHOLD', '0.70'))
    is_anomaly = anomaly_score > threshold

    result = {
        "event_id": data.get("event_id", "unknown"),
        "patient_id": data.get("patient_id", "unknown"),
        "anomaly_score": round(anomaly_score, 4),
        "is_anomaly": is_anomaly,
        "risk_level": (
            "critical" if anomaly_score > 0.80
            else "high" if anomaly_score > 0.60
            else "moderate" if anomaly_score > 0.35
            else "low"
        ),
        "model_version": model_version,
        "scoring_ms": round(scoring_ms, 2),
        "signals": {
            "vitals_risk": "high" if (heart_rate > 120 or spo2 < 90) else "moderate" if (heart_rate > 100 or spo2 < 95) else "low",
            "department_risk": department,
            "acuity_risk": patient_acuity,
            "hemodynamic_stability": "unstable" if systolic_bp > 180 or systolic_bp < 90 else "borderline" if systolic_bp > 140 else "stable",
        },
    }

    if is_anomaly:
        logger.warning(
            f"[HIPAA-AUDIT] CLINICAL ALERT: patient={result['patient_id']} "
            f"score={anomaly_score:.4f} dept={department}"
        )
    else:
        logger.info(f"Clinical event scored: event={result['event_id']} score={anomaly_score:.4f}")

    return jsonify(result)

@app.route('/api/v1/phi/access-audit', methods=['POST'])
def phi_access_audit():
    """Evaluate PHI access pattern for anomalous behavior (HIPAA §164.312)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    user_id = data.get("user_id", "unknown")
    access_count = data.get("access_count_last_hour", 0)
    department = data.get("department", "unknown")
    role = data.get("role", "unknown")

    # PHI access anomaly heuristics
    risk_score = 0.0

    # Excessive access volume
    if access_count > 50:
        risk_score += 0.40
    elif access_count > 20:
        risk_score += 0.15

    # Cross-department access
    if data.get("cross_department_access", False):
        risk_score += 0.25

    # After-hours access
    if data.get("after_hours", False):
        risk_score += 0.20

    # Bulk download pattern
    if data.get("bulk_export", False):
        risk_score += 0.35

    risk_score = min(risk_score, 1.0)
    is_suspicious = risk_score > 0.50

    if is_suspicious:
        logger.warning(
            f"[HIPAA-AUDIT] SUSPICIOUS PHI ACCESS: user={user_id} "
            f"dept={department} risk={risk_score:.2f} accesses={access_count}"
        )

    return jsonify({
        "user_id": user_id,
        "risk_score": round(risk_score, 4),
        "is_suspicious": is_suspicious,
        "recommendation": "investigate" if is_suspicious else "allow",
        "signals": {
            "volume": "high" if access_count > 50 else "moderate" if access_count > 20 else "normal",
            "cross_department": data.get("cross_department_access", False),
            "after_hours": data.get("after_hours", False),
            "bulk_export": data.get("bulk_export", False),
        },
    })

@app.route('/model/swap', methods=['POST'])
def swap_model():
    """Hot-swap the clinical anomaly detection model (for failover scenarios)."""
    global model_version
    data = request.get_json()
    new_version = data.get("model_version", "clinical_anomaly_v2")
    old_version = model_version
    model_version = new_version
    logger.info(f"Model hot-swap: {old_version} -> {new_version}")
    return jsonify({"previous": old_version, "current": model_version, "status": "swapped"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8094))
    logger.info(f"Clinical Decision Service starting on port {port} with model {model_version}")
    app.run(host='0.0.0.0', port=port)
