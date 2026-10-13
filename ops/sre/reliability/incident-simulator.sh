#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -euo pipefail
echo "Simulating incident…"
kubectl scale deployment express-app --replicas=0 -n apps
sleep 10
kubectl scale deployment express-app --replicas=2 -n apps
