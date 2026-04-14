#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
ERROR_RATE=$1
ALLOWED=$(echo "$ERROR_RATE < 0.01" | bc -l)
echo "Error rate within SLO: $ALLOWED"
