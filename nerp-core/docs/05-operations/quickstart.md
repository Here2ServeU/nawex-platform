# Quickstart (Local Demo)

This guide brings up the Express app, the AIOps orchestrator, and the robotics demo for interview-ready demos.

## Prerequisites
- Node.js 18+
- Python 3.10+
- Docker + Docker Compose
- jq (for JSON formatting in scripts)

## 1) Bootstrap
```bash
scripts/bootstrap.sh
```

## Unified DevSecOps Demo (Recommended)
Run the complete infrastructure demo in one command:
```bash
scripts/demo-devsecops.sh
```

Options:
- `--robotics`: Include robotics simulation
- `--aws-audit`: Show AWS SecurityHub/Config audit info

## Manual Setup Steps

For step-by-step control, use the following commands:
```bash
scripts/start_app.sh
```

## 3) Start the AIOps Orchestrator (Terminal B)
```bash
scripts/start_ai.sh
```

## 4) (Optional) Start the Robotics Demo (Terminal C)
```bash
scripts/start_robotics.sh
```

## 5) (Optional) Start Fintech Services (Terminal D)
```bash
scripts/start_fintech.sh
```

## 6) Generate Fintech Traffic (Terminal E)
```bash
# 30 seconds of transactions at 5 TPS
scripts/generate-transactions.sh 30 5
```

## 7) (Optional) Start Healthcare Services (Terminal F)
```bash
scripts/start_healthcare.sh
```

## 8) Generate Healthcare Traffic (Terminal G)
```bash
# 30 seconds of clinical events at 5 RPS
scripts/generate-ehr-events.sh 30 5
```

## 9) Validate
```bash
scripts/healthcheck.sh
```

## 10) Trigger Chaos
```bash
scripts/chaos_demo.sh

# Fintech-specific chaos
sre/chaos/payment-gateway-failure.sh
sre/chaos/transaction-fraud-spike.sh

# Healthcare-specific chaos
sre/chaos/ehr-gateway-failure.sh
sre/chaos/phi-breach-simulation.sh
```

## 11) Heal / Reset
```bash
scripts/heal.sh
```

## Notes
- The AI orchestrator reads config from `ai/agents/agent_config.yaml`.
- To read real app metrics, set `source: http` in that config.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
