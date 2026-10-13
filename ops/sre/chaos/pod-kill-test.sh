#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -euo pipefail
APP="${1:?usage: $0 <app-label>}"
POD="$(kubectl get pods -l "app=${APP}" -o jsonpath='{.items[0].metadata.name}')"
kubectl delete pod "$POD" --force --grace-period=0
