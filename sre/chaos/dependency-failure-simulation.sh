#!/bin/bash
kubectl scale deployment redis --replicas=0 -n apps
