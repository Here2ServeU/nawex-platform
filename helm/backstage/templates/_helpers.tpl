{{- define "backstage.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "backstage.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "backstage.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}
