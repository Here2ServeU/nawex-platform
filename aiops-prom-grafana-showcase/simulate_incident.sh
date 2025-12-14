#!/bin/bash
echo "SIMULATING OUTAGE & LATENCY SPIKE..."
URL="http://localhost:3000"

# 1. Generate 404 Errors (Bad Link)
echo "Generating 404s..."
for i in {1..20}; do
   curl -s -o /dev/null "$URL/api/broken-endpoint" &
done

# 2. Generate Saturation
echo "Generating Saturation..."
for i in {1..50}; do
   curl -s -o /dev/null "$URL/api/products" &
done

echo "Batch sent. Watch the dashboard!"
