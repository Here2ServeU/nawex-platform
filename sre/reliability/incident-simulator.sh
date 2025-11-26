#!/bin/bash
echo "Simulating incident…"
kubectl scale deployment express-app --replicas=0 -n apps
sleep 10
kubectl scale deployment express-app --replicas=2 -n apps
