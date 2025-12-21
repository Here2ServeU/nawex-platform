#!/bin/bash

# --- CONFIGURATION ---
AGENT_PROCESS="safety_interceptor.py"
LOG_FILE="../logs/agent_health.log"
CHECK_INTERVAL=5 # Seconds

echo "[$(date)] Starting Health Check Watchdog for $AGENT_PROCESS..."

# Ensure the logs directory exists
mkdir -p ../logs

while true; do
    # Check if the safety agent process is running
    if ! pgrep -f "$AGENT_PROCESS" > /dev/null; then
        echo "[$(date)] ALERT: $AGENT_PROCESS is down. Restarting..." >> "$LOG_FILE"
        
        # Action: Restart the agent in the background
        python3 "$AGENT_PROCESS" >> "$LOG_FILE" 2>&1 &
        
        echo "[$(date)] SUCCESS: $AGENT_PROCESS has been resurrected." >> "$LOG_FILE"
    else
        # Optional: Log heartbeat for forensic audit
        echo "[$(date)] HEARTBEAT: $AGENT_PROCESS is healthy." >> "$LOG_FILE"
    fi
    
    sleep "$CHECK_INTERVAL"
done
