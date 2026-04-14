#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
APP=$1
POD=$(kubectl get pods -l app=$APP -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod $POD --force --grace-period=0
