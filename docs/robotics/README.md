# Robotics Demo (Clinical Telemetry Loop)

This module simulates a **robotics telemetry stream** and a **safety watchdog** to demonstrate how the platform ingests edge signals and validates resilience behavior in real time.

## What It Shows
* **High-frequency telemetry** from a simulated surgical robot
* **gRPC service** acting as the “brain” for ingest/processing
* **Safety watchdog** that verifies agent health and logs the results

## Components
* **surgical-brain**: gRPC server that ingests telemetry
* **surgical-robot**: gRPC client that emits telemetry
* **safety-watchdog**: health check runner for agents

## Run the Robotics Demo
```bash
docker compose --profile robotics up -d
```

## Run from One-Click Demo
```bash
DEMO_ROBOTICS=1 bash make demo
```

## Logs & Outputs
- Docker logs for each container
- Local log volume: `robotics/logs/`

## Talking Point
“This demo proves the AIOps pipeline can ingest **edge telemetry** in a healthcare setting and validate safety agent availability under load.”

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
