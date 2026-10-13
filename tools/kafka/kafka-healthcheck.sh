#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -euo pipefail

fail=0

if [[ ! -f deploy/k8s/kafka-zookeeper.yaml ]]; then
    echo "[policy] missing deploy/k8s/kafka-zookeeper.yaml"
    fail=1
else
    if grep -q "type: NodePort" deploy/k8s/kafka-zookeeper.yaml; then
        echo "[policy] kafka service must not be NodePort"
        fail=1
    fi
    if grep -q "type: LoadBalancer" deploy/k8s/kafka-zookeeper.yaml; then
        echo "[policy] kafka service must not be LoadBalancer"
        fail=1
    fi
fi

if [[ ! -f docs/guides/devsecops-integration.md ]]; then
    echo "[policy] missing docs/guides/devsecops-integration.md"
    fail=1
fi

if [[ ! -f docs/architecture/06-quantum-optimization-layer.md ]]; then
    echo "[policy] missing docs/architecture/06-quantum-optimization-layer.md"
    fail=1
fi

if [[ "$fail" -ne 0 ]]; then
    echo "[policy] failed"
    exit 1
fi

echo "[policy] passed"
