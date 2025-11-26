#!/bin/bash
TARGET=$1
kubectl exec -it $(kubectl get pods -l app=$TARGET -o jsonpath='{.items[0].metadata.name}')  -- tc qdisc add dev eth0 root netem delay 300ms
