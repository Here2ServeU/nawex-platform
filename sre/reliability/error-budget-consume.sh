#!/bin/bash
ERROR_RATE=$1
ALLOWED=$(echo "$ERROR_RATE < 0.01" | bc -l)
echo "Error rate within SLO: $ALLOWED"
