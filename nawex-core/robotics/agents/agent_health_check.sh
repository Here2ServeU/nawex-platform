#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
# --- CONFIGURATION ---
AGENT_PROCESS="safety_interceptor.py"
LOG_FILE="../logs/agent_health.log"
CHECK_INTERVAL=5 
MAX_RETRIES=5
RETRY_COUNT=0
# Replace with your actual Slack Webhook URL
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Ensure robust path handling
cd "$(dirname "$0")"
mkdir -p ../logs

echo "[$(date)] Starting Reliability Watchdog for $AGENT_PROCESS..." | tee -a "$LOG_FILE"

send_alert() {
    local message="$1"
    echo "[$(date)] SENDING ALERT: $message" >> "$LOG_FILE"
    # Payload for Slack notification
    curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"*AIOPS ALERT:* $message\"}" "$SLACK_WEBHOOK_URL" > /dev/null 2>&1
}

while true; do
    if ! pgrep -f "$AGENT_PROCESS" > /dev/null; then
        RETRY_COUNT=$((RETRY_COUNT + 1))
        
        echo "[$(date)] ALERT: $AGENT_PROCESS is down (Attempt $RETRY_COUNT/$MAX_RETRIES)." >> "$LOG_FILE"
        send_alert "Process $AGENT_PROCESS is down. Attempting resurrection $RETRY_COUNT/$MAX_RETRIES."

        if [ "$RETRY_COUNT" -le "$MAX_RETRIES" ]; then
            python3 "$AGENT_PROCESS" >> "$LOG_FILE" 2>&1 &
            sleep 2
            if pgrep -f "$AGENT_PROCESS" > /dev/null; then
                echo "[$(date)] SUCCESS: $AGENT_PROCESS resurrected." >> "$LOG_FILE"
                RETRY_COUNT=0
            fi
        else
            echo "[$(date)] CRITICAL: Max retries reached. Manual intervention required." >> "$LOG_FILE"
            send_alert "CRITICAL: $AGENT_PROCESS failed to restart after $MAX_RETRIES attempts. System may be unstable."
            # Optional: exit 1 to let an orchestrator like Kubernetes/Docker handle the container restart
        fi
    else
        # Periodic Heartbeat for forensic audit
        echo "[$(date)] HEARTBEAT: $AGENT_PROCESS is healthy." >> "$LOG_FILE"
        RETRY_COUNT=0
    fi
    
    sleep "$CHECK_INTERVAL"
done
