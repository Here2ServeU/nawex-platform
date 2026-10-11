# Golden Platform — every workflow an engineer needs, one verb each.  `make help` lists them.
SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

PYTHON  ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
GOLDEN  := $(BIN)/golden
CFG      = $(shell $(GOLDEN) config get $(1) 2>/dev/null || echo $(2))

# Defaults come from platform.yaml; override on the command line, e.g. `make deploy CLOUD=gcp ENV=prod`.
CLOUD   ?= $(call CFG,cloud.provider,local)
ENV     ?= $(call CFG,cloud.environment,dev)
IMAGE   ?= golden-platform
TAG     ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)
APPS    := apps/client-portal apps/workload

.PHONY: help
help: ## Show this help
	@awk 'BEGIN{FS=":.*##"; printf "\nUsage: make <target> [CLOUD=aws|azure|gcp|openshift|local] [ENV=dev|staging|prod]\n\n"} \
	  /^##@/{printf "\n\033[1m%s\033[0m\n", substr($$0,5)} /^[a-zA-Z0-9_-]+:.*##/{printf "  \033[36m%-22s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

##@ Setup
.PHONY: bootstrap doctor
bootstrap: ## Create .venv, install Python (dev+ml) and Node deps, install pre-commit hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e '.[dev,ml,robotics]'
	for app in $(APPS); do npm --prefix $$app ci; done
	-$(BIN)/pre-commit install 2>/dev/null || true
	@echo "✓ bootstrap complete — next: make test && make up"

doctor: ## Check local prerequisites and accelerator availability
	@for t in python3 node npm docker git terraform helm kubectl; do \
	  if command -v $$t >/dev/null; then printf "  ✓ %s\n" $$t; else printf "  ✗ %s (missing)\n" $$t; fi; done
	@$(GOLDEN) gpu doctor
	@$(GOLDEN) config show >/dev/null && echo "  ✓ platform.yaml valid"

##@ Quality
.PHONY: lint format typecheck test test-ml test-apps check
lint: ## Lint Python (ruff) and Node apps (eslint)
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests
	for app in $(APPS); do npm --prefix $$app run lint; done

format: ## Auto-format Python
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

typecheck: ## Static type check (mypy)
	$(BIN)/mypy

test: ## Python tests with coverage gate
	$(BIN)/pytest --cov --cov-report=term --cov-report=xml

test-ml: ## Only the deep-learning / GPU tests
	$(BIN)/pytest -m ml -v

test-apps: ## Node app tests
	for app in $(APPS); do npm --prefix $$app test; done

check: lint typecheck test test-apps validate-infra ## Everything CI runs

##@ Run locally
.PHONY: up down logs up-observability demo orchestrate
up: ## Build and start the whole platform with Docker Compose
	docker compose up -d --build
	@echo "API http://localhost:8000/docs · Portal http://localhost:3001 · Workload http://localhost:8080"

down: ## Stop the platform
	docker compose --profile robotics down --remove-orphans

logs: ## Tail platform logs
	docker compose logs -f --tail=100

up-observability: ## Start Prometheus/Grafana/Loki/Tempo next to the platform
	docker compose -f observability/docker-compose.yml up -d

demo: ## Narrated executive demo for all four domains (HTML reports in demo_output/)
	$(GOLDEN) demo client --vertical all --client "$${CLIENT:-Demo Client}"

orchestrate: ## Run the governed AIOps loop for 5 cycles
	$(GOLDEN) orchestrate --cycles 5 --interval 2

##@ AI / GPU
.PHONY: train security-status proto
proto: ## Regenerate robotics gRPC stubs from proto/
	$(BIN)/python -m grpc_tools.protoc -Iproto --python_out=src/golden/robotics/grpc/generated \
	  --grpc_python_out=src/golden/robotics/grpc/generated --pyi_out=src/golden/robotics/grpc/generated \
	  proto/surgical_telemetry.proto
	sed -i.bak 's/^import surgical_telemetry_pb2 as/from golden.robotics.grpc.generated import surgical_telemetry_pb2 as/' \
	  src/golden/robotics/grpc/generated/surgical_telemetry_pb2_grpc.py && rm -f src/golden/robotics/grpc/generated/*.bak

train: ## Train LSTM+TCN (uses CUDA/MPS automatically) and write the integrity manifest
	$(GOLDEN) train --model all --epochs $${EPOCHS:-3} --output-dir models

security-status: ## Show autonomy mode, kill switch, caps and audit-chain status
	$(GOLDEN) security status

##@ VMware → OpenShift migration
.PHONY: migrate-assess migrate-plan migrate-manifests
INVENTORY ?= $(call CFG,migration.inventory,)
INV_ARG   = $(if $(INVENTORY),--inventory $(INVENTORY),)
migrate-assess: ## Assess readiness (INVENTORY=path/to/rvtools-export or sample estate)
	$(GOLDEN) migrate assess $(INV_ARG)

migrate-plan: ## Plan dependency-aware migration waves
	$(GOLDEN) migrate plan $(INV_ARG)

migrate-manifests: ## Generate MTV Plan/Migration/Network/StorageMap per wave for GitOps
	$(GOLDEN) migrate manifests $(INV_ARG) --output deploy/openshift/virtualization/waves

##@ Build & deploy
.PHONY: build validate-infra plan deploy destroy
build: ## Build all container images
	docker build -t $(IMAGE):$(TAG) .
	docker build -t golden-client-portal:$(TAG) apps/client-portal
	docker build -t golden-workload:$(TAG) apps/workload

validate-infra: ## helm lint/template + kubeconform + terraform fmt/validate
	scripts/ci/validate-infra.sh

plan: ## Terraform plan for CLOUD/ENV (no changes)
	scripts/deploy.sh $(CLOUD) $(ENV) plan

deploy: ## Landing zone (Terraform) + platform (Helm) on CLOUD/ENV
	IMAGE_TAG=$(TAG) scripts/deploy.sh $(CLOUD) $(ENV) apply

destroy: ## Tear down CLOUD/ENV
	scripts/deploy.sh $(CLOUD) $(ENV) destroy

##@ Template
.PHONY: init clean
init: ## Rebrand the template: make init SLUG=acme NAME="Acme Platform"
	scripts/init-project.sh $(SLUG) "$(NAME)"

clean: ## Remove caches and build output
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov build dist .artifacts demo_output
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
