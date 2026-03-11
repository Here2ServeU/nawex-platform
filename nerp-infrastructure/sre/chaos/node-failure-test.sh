#!/usr/bin/env bash
# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
NODE=$1
kubectl cordon $NODE
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data
