#!/bin/bash
NODE=$1
kubectl cordon $NODE
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data
