#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
#
# Synthetic Test Runner (Smoke Test)
# Description: Performs a robust HTTP health check against a target endpoint.
# Used as a Quality Gate in CI/CD pipelines to verify deployment success.
# Usage: ./synthetic-test-run.sh -u <url> [-t <timeout_ms>] [-r <retries>]
#

set -euo pipefail

# --- Configuration & Colors ---
DEFAULT_URL="http://localhost:8000/health" # platform API (golden serve api)
DEFAULT_TIMEOUT_MS=2000 # 2 seconds
DEFAULT_RETRIES=5
DEFAULT_MATCH_STRING='"status":"ok"' # Expect JSON health response

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

usage() {
    echo -e "${BLUE}Usage:${NC} $0 [OPTIONS]"
    echo -e "\nOptions:"
    echo -e " -u, --url <url> Target URL to test (Default: $DEFAULT_URL)"
    echo -e " -s, --search <string> String to search for in response body (Default: '$DEFAULT_MATCH_STRING')"
    echo -e " -l, --latency <ms> Max allowed latency in ms (Default: $DEFAULT_TIMEOUT_MS)"
    echo -e " -r, --retries <count> Number of retries before failing (Default: $DEFAULT_RETRIES)"
    echo -e " -h, --help Show this help message"
    echo -e "\n${BLUE}Example:${NC}"
    echo -e " $0 -u https://api.myapp.com/health -r 10"
    echo -e " $0 --url http://localhost:8080 --search 'Welcome'"
    exit 1
}
