#!/bin/bash
echo "Generating healthy baseline traffic..."
URL="http://localhost:3000" # Ensure this matches your App port

while true; do
  # Simulating successful user behavior
  curl -s -o /dev/null -w "%{http_code} " "$URL/api/health"
  curl -s -o /dev/null -w "%{http_code} " "$URL/api/products"
  echo "."
  sleep 0.5 
done
