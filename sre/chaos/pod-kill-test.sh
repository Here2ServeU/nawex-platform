#!/bin/bash
APP=$1
POD=$(kubectl get pods -l app=$APP -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod $POD --force --grace-period=0
