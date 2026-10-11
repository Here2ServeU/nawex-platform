# Healthcare Services Module

This document describes the microservices for the **Healthcare** vertical of the Golden Platform. These services handle electronic health record (EHR) ingestion, clinical decision support, and FHIR/HL7-compliant patient data exchange.

## Services

### EHR Ingestion Service (`ehr-ingestion`)
- **Port**: 8093
- **Purpose**: Core clinical data ingestion service that receives, validates, and routes EHR/FHIR resources through the platform.
- **Features**: FHIR R4 resource validation, HIPAA-audit logging for all PHI access, Kafka-backed event streaming, multi-department routing.

### Clinical Decision Support (`clinical-decision`)
- **Port**: 8094
- **Purpose**: Real-time ML-based clinical anomaly detection and patient vital monitoring using LSTM/TCN models.
- **Features**: Sub-30ms vital sign scoring, PHI access anomaly detection, configurable thresholds, automatic model hot-swap.
- **Pipeline**: Uses `src/golden/ai/pipelines/detect_phi_anomalies.py` for anomaly logic.

### Patient Data Gateway (`patient-data-gateway`)
- **Port**: 8095
- **Purpose**: Simulates FHIR R4/HL7 v2 gateway interactions for clinical data exchange, consent management, and interoperability.
- **Features**: Configurable latency/error injection, patient consent verification (HIPAA §164.508), multi-EHR system connectivity.

### Healthcare Redis (`healthcare-redis`)
- **Port**: 6381
- **Purpose**: Dedicated high-performance cache for clinical session state, PHI access tokens, and real-time vital sign buffers.

### Healthcare Watchdog (`healthcare-watchdog`)
- **Purpose**: Continuous compliance monitoring for clinical SLOs, patient safety alerts, EHR latency, and HIPAA audit trail integrity.

## Quick Start

```bash
# Start all healthcare services (requires Kafka)
docker compose up -d ehr-ingestion clinical-decision patient-gateway

# Or use the convenience script
make up
```

## Compliance

These services are designed to comply with:
- **HIPAA** — Protected Health Information security and privacy
- **HITECH** — Electronic health record incentive and breach notification
- **HDS** — French Health Data Hosting certification
- **SOC 2** — Security, availability, and confidentiality controls
- **FDA 21 CFR Part 11** — Electronic records and signatures for clinical systems

See `/docs/compliance/` for detailed compliance mappings.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
