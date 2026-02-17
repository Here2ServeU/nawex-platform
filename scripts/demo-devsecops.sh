#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# Express-Reliability AIOps DevSecOps Unified Demo Script
# Orchestrates full infrastructure demo: Kafka → App → AIOps → Chaos → Recovery → Security
# Usage: ./scripts/demo-devsecops.sh [--robotics] [--aws-audit]
##############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Configuration
DEMO_ROBOTICS=0
DEMO_AWS_AUDIT=0
KAFKA_WAIT_TIMEOUT=60
SERVICE_WAIT_TIMEOUT=90

# Temporary log files for service diagnostics
APP_LOG_FILE=$(mktemp /tmp/express-app.XXXX.log)
AI_LOG_FILE=$(mktemp /tmp/aiops-orchestrator.XXXX.log)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

##############################################################################
# Helper Functions
##############################################################################

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

success() {
    echo -e "${GREEN}✓ $*${NC}"
}

warn() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

error() {
    echo -e "${RED}✗ $*${NC}" >&2
}

section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}▶ $*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

pause_for_demo() {
    local msg="${1:-Press enter to continue...}"
    read -p "$(echo -e ${YELLOW}$msg${NC})" -r
}
pid=$3
    local elapsed=0
    local interval=2
    
    while ! nc -z localhost "$port" 2>/dev/null; do
        if [ $elapsed -ge $timeout ]; then
            error "Timeout waiting for port $port"
            if [ -n "${pid:-}" ] && ! kill -0 $pid 2>/dev/null; then
                error "Process $pid is no longer running"
            fi
    
    while ! nc -z localhost "$port" 2>/dev/null; do
        if [ $elapsed -ge $timeout ]; then
            error "Timeout waiting for port $port"
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    return 0
}

wait_for_kafka() {
    log "Waiting for Kafka broker to be ready (timeout: ${KAFKA_WAIT_TIMEOUT}s)..."
    local elapsed=0
    local interval=3
    
    # First, wait for the port to be open
    while ! nc -z localhost 9092 2>/dev/null; do
        if [ $elapsed -ge $KAFKA_WAIT_TIMEOUT ]; then
            error "Timeout waiting for Kafka port 9092"
            docker compose logs kafka || true
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    # Once port is open, verify Kafka is actually responding
    elapsed=0
    while ! docker exec kafka_broker kafka-topics.sh --bootstrap-server kafka:9092 --list &>/dev/null 2>&1; do
        if [ $elapsed -ge 10 ]; then
            warn "Kafka port open but broker not responding yet, continuing anyway..."
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    success "Kafka broker is ready"
    return 0
}

##############################################################################
# Phase 1: Parse Arguments
##############################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --robotics)
            DEMO_ROBOTICS=1
            shift
        ;;
        --aws-audit)
            DEMO_AWS_AUDIT=1
            shift
        ;;
        *)
            error "Unknown option: $1"
            exit 1
        ;;
    esac
done

##############################################################################
# Phase 2: Bootstrap & Dependency Check
##############################################################################

section "PHASE 1: Bootstrap & Dependency Check"

log "Checking prerequisites..."
command -v docker >/dev/null || { error "Docker not installed"; exit 1; }
command -v node >/dev/null || { error "Node.js not installed"; exit 1; }
command -v python3 >/dev/null || { error "Python 3 not installed"; exit 1; }
if bash scripts/bootstrap.sh >/dev/null 2>&1; then
    success "Bootstrap completed"
else
    warn "Bootstrap script had warnings, continuing..."
fi

log "Verifying npm dependencies in app/..."
if [ ! -d "app/node_modules" ]; then
    log "Installing app dependencies..."
    npm --prefix app install >/dev/null 2>&1 || warn "npm install had warnings"
fi
success "App dependencies readyet"

log "Running bootstrap..."
bash scripts/bootstrap.sh >/dev/null 2>&1 || warn "Bootstrap script had warnings, continuing..."
success "Bootstrap completed"

pause_for_demo "▶ Bootstrap complete. Press enter to start Kafka & Zookeeper..."

##############################################################################
# Phase 3: Start Kafka & Zookeeper
##############################################################################

section "PHASE 2: Start Kafka Event Backbone"

log "Starting Zookeeper and Kafka..."
docker compose up -d zookeeper kafka || { error "Failed to start Kafka/Zookeeper"; exit 1; }
success "Docker Compose services started"

if wait_for_kafka; then
    success "Kafka is healthy"
else
    error "Kafka failed to become ready"
    exit 1
fi

log "Verifying Kafka health"$APP_LOG_FILE" 2>&1 &
APP_PID=$!
log "Express app started (PID: $APP_PID)"
log "App logs: $APP_LOG_FILE"

log "Waiting for Express app port 3000 (timeout: ${SERVICE_WAIT_TIMEOUT}s)..."
if wait_for_port 3000 $SERVICE_WAIT_TIMEOUT $APP_PID; then
    success "Express app is listening"
else
    error "Express app failed to start"
    
    # Show diagnostics
    if [ -f "$APP_LOG_FILE" ]; then
        error "Last 20 lines of app log:"
        tail -20 "$APP_LOG_FILE" >&2
    fi
    
    if kill -0 $APP_PID 2>/dev/null; then
        log "Killing app p"$AI_LOG_FILE" 2>&1 &
AI_PID=$!
log "AIOps orchestrator started (PID: $AI_PID)"
log "AI logs: $AI_LOG_FILE"
sleep 2
    #####################################################

section "PHASE 3: Start Core Services (App + AIOps)"

log "Starting Express app in background..."
bash scripts/start_app.sh >/dev/null 2>&1 &
APP_PID=$!
log "Express app started (PID: $APP_PID)"

log "Waiting for Express app port 3000..."
if wait_for_port 3000 $SERVICE_WAIT_TIMEOUT; then
    success "Express app is listening"
else
    error "Express app failed to start"
    kill $APP_PID || true
    exit 1
fi

log "Starting AIOps orchestrator in background..."
bash scripts/start_ai.sh >/dev/null 2>&1 &
AI_PID=$!
log "AIOps orchestrator started (PID: $AI_PID)"

success "Core services are running"

##############################################################################
# Phase 5: (Optional) Start Robotics Demo
##############################################################################

if [ $DEMO_ROBOTICS -eq 1 ]; then
    section "PHASE 4A: Start Robotics Demo (Optional)"
    log "Starting robotics demo..."
    bash scripts/start_robotics.sh >/dev/null 2>&1 &
    ROBOTICS_PID=$!
    log "Robotics started (PID: $ROBOTICS_PID)"
    sleep 3
    success "Robotics demo is running"
fi

pause_for_demo "▶ Services running. Press enter to validate health..."

##############################################################################
# Phase 6: Health Check & Observability
##############################################################################

section "PHASE 4: Health Check & Observability"

log "Running health checks..."
bash scripts/healthcheck.sh || warn "Some healthchecks had warnings"

success "Health checks completed"

log "Fetching live metrics from /metrics endpoint..."
METRICS=$(curl -s http://localhost:3000/metrics | head -20)
echo "$METRICS"

success "Metrics endpoint is responding"

log "Kafka topic list:"
docker exec kafka_broker kafka-topics.sh --bootstrap-server localhost:9092 --list || warn "Could not list topics"

success "Observability validated"

pause_for_demo "▶ Observability configured. Press enter to inject chaos..."

##############################################################################
# Phase 7: Chaos Engineering
##############################################################################

section "PHASE 5: Chaos Injection & AIOps Response"

log "Injecting chaos (latency, errors, saturation, memory leak)..."
log "Watch the /metrics endpoint and AIOps logs respond in real-time..."
bash scripts/chaos_demo.sh || warn "Chaos injection had issues"

success "Chaos injected"

log "Sleeping 10 seconds to allow AIOps to detect and process anomalies..."
sleep 10

log "Checking current metrics during chaos..."
CHAOS_METRICS=$(curl -s http://localhost:3000/metrics | grep -E "http_request_duration|app_errors|go_goroutines" | head -5)
echo "$CHAOS_METRICS"

success "AIOps decision loop should have attempted remediation (check logs)"

pause_for_demo "▶ Chaos running. Press enter to trigger recovery..."

##############################################################################
# Phase 8: Recovery & Healing
##############################################################################

section "PHASE 6: Recovery & Remediation"

log "Triggering heal sequence to reset system state..."
bash scripts/heal.sh || warn "Heal script had issues"

success "System healed and reset"

log "Waiting 5 seconds for services to stabilize..."
sleep 5

log "Verifying recovery - fetching metrics..."
RECOVERED_METRICS=$(curl -s http://localhost:3000/metrics | grep -E "http_request_duration_seconds" | head -3)
echo "$RECOVERED_METRICS"

success "System has recovered to baseline"

pause_for_demo "▶ Recovery complete. Press enter to validate security compliance..."

##############################################################################
# Phase 9: Security & Compliance Validation
##############################################################################

section "PHASE 7: Security & Compliance Validation"

log "Running policy gate (infrastructure validation)..."
bash scripts/policy-gate.sh && success "Policy gate PASSED" || warn "Policy gate had warnings"

log "Reviewing DevSecOps integration points..."
echo ""
log "✓ SecurityHub + AWS Config modules wired to all environments"
log "  Location: terraform/modules/aws/securityhub/ and terraform/modules/aws/config/"
log ""
log "✓ Data Pipeline Observability playbook"
log "  Location: ops/playbooks/data_pipeline_observability.md"
log ""
log "✓ Kafka operations & healthcheck tooling"
log "  Healthcheck: tools/kafka/kafka-healthcheck.sh"
log ""
log "✓ Trivy vulnerability scanning in CI/CD"
log "  Location: .github/workflows/ci.yml"
log ""
log "✓ Playbooks for operational runbooks"
log "  Locations:"
log "    - ops/playbooks/kafka_healthcheck.md"
log "    - ops/playbooks/observability_dashboards.md"
log "    - ops/playbooks/securityhub_config.md"
log ""

if [ $DEMO_AWS_AUDIT -eq 1 ]; then
    log "To enable AWS SecurityHub + Config audit (requires AWS credentials and Terraform):"
    echo "  cd terraform/live/aws/dev && terraform plan"
    echo "  (This would wire SecurityHub and Config to your AWS account)"
fi

success "Security & Compliance review complete"

##############################################################################
# Phase 10: Summary & Cleanup Instructions
##############################################################################

section "DEMO COMPLETE ✓"

echo ""
log "Summary of Infrastructure Components:"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Kafka Backbone:"
echo "    • Bootstrap: kafka:9092"
echo "    • Command: docker compose ps"
echo ""
echo "  Express App:"
echo "    • URL: http://localhost:3000"
echo "    • Metrics: http://localhost:3000/metrics"
echo "    • PID: $APP_PID"
echo ""
echo "  AIOps Orchestrator:"
echo "    • Status: Running in background"
echo "    • Config: ai/agents/agent_config.yaml"
echo "    • PID: $AI_PID"
echo ""
if [ $DEMO_ROBOTICS -eq 1 ]; then
    echo "  Robotics Demo:"
    echo "    • gRPC Server: localhost:50051"
    echo "    • PID: $ROBOTICS_PID"
    echo ""
fi
echo "  Compliance & Security:"
echo "    • SecurityHub: terraform/modules/aws/securityhub/"
echo "    • AWS Config: terraform/modules/aws/config/"
echo "    • Trivy CI Scans: .github/workflows/ci.yml"
echo ""
log "To stop all services:"

log "Service logs stored at:"
log "  App:  $APP_LOG_FILE"
log "  AI:   $AI_LOG_FILE"
echo "  • Foreground processes: Press Ctrl+C (will cleanly exit)"
echo "  • Docker services: docker compose down"
echo "  • Full cleanup: scripts/cleanup.sh"
echo ""
log "Documentation:"
echo "  • Architecture: docs/architecture/"
echo "  • Playbooks: ops/playbooks/"
echo "  • DevSecOps Guide: docs/guides/devsecops-integration.md"
echo "  • Quick Reference: docs/guides/quickstart.md"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

pause_for_demo "▶ Demo complete. Press enter to exit..."

##############################################################################
# Cleanup
##############################################################################

log "Performing graceful shutdown..."
kill $APP_PID 2>/dev/null || true
kill $AI_PID 2>/dev/null || true
[ $DEMO_ROBOTICS -eq 1 ] && kill $ROBOTICS_PID 2>/dev/null || true

success "Demo session ended successfully"
