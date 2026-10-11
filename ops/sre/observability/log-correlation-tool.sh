#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
#
# Log Correlation Tool
# Description: specific CLI utility to search and correlate application logs using Trace IDs or Correlation IDs.
# Usage: ./log-correlation-tool.sh -t <trace_id> [-d <log_dir>]
#

set -euo pipefail

# --- Configuration & Colors ---
DEFAULT_LOG_DIR="/var/log/app"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---

usage() {
    echo -e "${BLUE}Usage:${NC} $0 [OPTIONS]"
    echo -e "\nOptions:"
    echo -e " -t, --trace-id <id> Search by Datadog Trace ID"
    echo -e " -c, --correlation-id <id> Search by Custom Correlation ID (UUID)"
    echo -e " -d, --dir <path> Log directory to search (Default: $DEFAULT_LOG_DIR)"
    echo -e " -h, --help Show this help message"
    echo -e "\n${BLUE}Example:${NC}"
    echo -e " $0 -t 1234567890"
    echo -e " $0 -c a1b2c3d4-e5f6 -d ./logs"
    exit 1
}

check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}[WARN] 'jq' is not installed.${NC} Output will be raw text instead of formatted JSON."
        HAS_JQ=false
    else
        HAS_JQ=true
    fi
}

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Argument Parsing ---

TRACE_ID=""
CORRELATION_ID=""
SEARCH_DIR="$DEFAULT_LOG_DIR"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--trace-id) TRACE_ID="$2"; shift ;;
        -c|--correlation-id) CORRELATION_ID="$2"; shift ;;
        -d|--dir) SEARCH_DIR="$2"; shift ;;
        -h|--help) usage ;;
        *) log_error "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# --- Validation ---

if [[ -z "$TRACE_ID" && -z "$CORRELATION_ID" ]]; then
    log_error "You must provide either a Trace ID (-t) or a Correlation ID (-c)."
    usage
fi

if [[ ! -d "$SEARCH_DIR" ]]; then
    log_error "Log directory '$SEARCH_DIR' does not exist."
    exit 1
fi

check_dependencies

# --- Execution ---

SEARCH_TERM=""
if [[ -n "$TRACE_ID" ]]; then
    SEARCH_TERM="$TRACE_ID"
    log_info "Searching for Trace ID: $TRACE_ID in $SEARCH_DIR..."
else
    SEARCH_TERM="$CORRELATION_ID"
    log_info "Searching for Correlation ID: $CORRELATION_ID in $SEARCH_DIR..."
fi

# Search logic
# 1. Grep recursively for the ID
# 2. If jq exists, parse and colorize; otherwise print raw line
if [[ "$HAS_JQ" == "true" ]]; then
    grep -r "$SEARCH_TERM" "$SEARCH_DIR" | while read -r line; do
        # Extract filename (before the first colon) and JSON content (after the first colon)
        FILENAME=$(echo "$line" | cut -d: -f1)
        JSON_CONTENT=$(echo "$line" | cut -d: -f2-)
        
        echo -e "\n${YELLOW}File: $FILENAME${NC}"
        # Attempt to pretty print; fall back to raw if JSON is invalid
        echo "$JSON_CONTENT" | jq -C . 2>/dev/null || echo "$JSON_CONTENT"
    done
else
    grep -r --color=always "$SEARCH_TERM" "$SEARCH_DIR"
fi

echo -e "\n${GREEN}Search complete.${NC}"
