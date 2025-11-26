#!/bin/bash
echo "Correlating logs with trace IDs..."
grep -R "trace_id" /var/log/app/
