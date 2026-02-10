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

## One-Click Demo Launcher
```bash
scripts/demo.sh
```

To include robotics:
```bash
DEMO_ROBOTICS=1 bash scripts/demo.sh
```

## 2) Start the Express App (Terminal A)
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

## 5) Validate
```bash
scripts/healthcheck.sh
```

## 6) Trigger Chaos
```bash
scripts/chaos_demo.sh
```

## 7) Heal / Reset
```bash
scripts/heal.sh
```

## Notes
- The AI orchestrator reads config from `ai/agents/agent_config.yaml`.
- To read real app metrics, set `source: http` in that config.
