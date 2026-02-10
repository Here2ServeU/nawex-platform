SHELL := /bin/bash
.RECIPEPREFIX := >

.PHONY: help bootstrap app-start ai-start robotics-start health chaos heal traffic demo

help:
> @echo "Express Reliability AIOps Platform"
> @echo "Targets:"
> @echo "  bootstrap       Install app deps and AI venv"
> @echo "  demo            One-click demo launcher"
> @echo "  app-start       Start the Express app"
> @echo "  ai-start        Start the AI orchestrator"
> @echo "  robotics-start  Start robotics demo via Docker Compose"
> @echo "  health          Run app health checks"
> @echo "  chaos           Trigger chaos demo"
> @echo "  heal            Reset app chaos state"
> @echo "  traffic         Generate load"

bootstrap:
> scripts/bootstrap.sh

app-start:
> scripts/start_app.sh

ai-start:
> scripts/start_ai.sh

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
