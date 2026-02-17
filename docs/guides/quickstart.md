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
