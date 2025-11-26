{{- define "otel-collector.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "otel-collector.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "otel-collector.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}
