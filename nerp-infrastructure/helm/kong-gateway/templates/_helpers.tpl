{{- define "kong-gateway.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "kong-gateway.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "kong-gateway.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}
