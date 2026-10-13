{{- define "express-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "express-app.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "express-app.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}
