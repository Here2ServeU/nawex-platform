#!/bin/bash
helm repo add datadog https://helm.datadoghq.com
helm upgrade --install dd-agent datadog/datadog -n observability   --set datadog.apiKey=$DD_API_KEY   --set datadog.site="datadoghq.com"
