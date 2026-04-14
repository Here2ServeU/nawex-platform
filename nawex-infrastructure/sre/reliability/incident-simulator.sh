#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
echo "Simulating incident…"
kubectl scale deployment express-app --replicas=0 -n apps
sleep 10
kubectl scale deployment express-app --replicas=2 -n apps
