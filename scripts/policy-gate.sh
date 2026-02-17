#!/usr/bin/env bash
set -euo pipefail

fail=0

if [[ ! -f k8s/kafka-zookeeper.yaml ]]; then
    echo "[policy] missing k8s/kafka-zookeeper.yaml"
    fail=1
else
    if grep -q "type: NodePort" k8s/kafka-zookeeper.yaml; then
        echo "[policy] kafka service must not be NodePort"
        fail=1
    fi
    if grep -q "type: LoadBalancer" k8s/kafka-zookeeper.yaml; then
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
