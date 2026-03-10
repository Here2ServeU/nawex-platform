SHELL := /bin/bash
.RECIPEPREFIX := >

.PHONY: help bootstrap app-start ai-start platform-start robotics-start health chaos heal traffic demo structure-check security-suite security-deps security-secrets security-iac security-container security-images security-policies

help:
> @echo "Express Reliability AIOps Platform"
> @echo "Targets:"
> @echo "  bootstrap       Install app deps and AI venv"
> @echo "  demo            One-click demo launcher"
> @echo "  app-start       Start the Express app"
> @echo "  ai-start        Start the AI orchestrator"
> @echo "  platform-start  Start platform domains together"
> @echo "  robotics-start  Start robotics demo via Docker Compose"
> @echo "  health          Run app health checks"
> @echo "  chaos           Trigger chaos demo"
> @echo "  heal            Reset app chaos state"
> @echo "  traffic         Generate load"
> @echo "  security-suite  Run all security checks"
> @echo "  structure-check Validate canonical path policy"
> @echo "  security-deps   Run dependency audit checks"
> @echo "  security-secrets Run repository secrets scan"
> @echo "  security-iac    Run IaC misconfiguration scan"
> @echo "  security-container Run container image scan wrapper"
> @echo "  security-images Run domain image scan list"
> @echo "  security-policies Validate policy-as-code artifacts"

bootstrap:
> scripts/bootstrap.sh

app-start:
> scripts/start_app.sh

ai-start:
> scripts/start_ai.sh

platform-start:
> scripts/start_platform.sh

robotics-start:
> scripts/start_robotics.sh

health:
> scripts/healthcheck.sh

chaos:
> scripts/chaos_demo.sh

heal:
> scripts/heal.sh

traffic:
> scripts/generate-traffic.sh

demo:
> scripts/demo.sh

structure-check:
> scripts/check-canonical-structure.sh

security-suite:
> security/scripts/run-security-suite.sh

security-deps:
> security/scripts/dependency-audit.sh

security-secrets:
> security/scripts/secrets-scan.sh

security-iac:
> security/scripts/iac-scan.sh

security-container:
> security/scripts/container-scan.sh

security-images:
> security/container-scanning/scan-images.sh

security-policies:
> security/policies/validate-policies.sh
