#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
TARGET=$1
kubectl exec -it $(kubectl get pods -l app=$TARGET -o jsonpath='{.items[0].metadata.name}') -- tc qdisc add dev eth0 root netem delay 300ms
