{{- define "splunk-hec.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "splunk-hec.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "splunk-hec.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}
