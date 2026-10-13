{{/*
Chart name.
*/}}
{{- define "golden.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified release name.
*/}}
{{- define "golden.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "golden.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels shared by every object of the release.
*/}}
{{- define "golden.labels" -}}
helm.sh/chart: {{ include "golden.chart" . }}
app.kubernetes.io/part-of: golden
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Object name for one service: <fullname>-<service>.
Usage: include "golden.serviceName" (dict "root" $ "name" $name)
*/}}
{{- define "golden.serviceName" -}}
{{- printf "%s-%s" (include "golden.fullname" .root) .name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Selector labels for one service.
*/}}
{{- define "golden.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Full labels for one service.
*/}}
{{- define "golden.serviceLabels" -}}
{{ include "golden.labels" .root }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/component: {{ .name }}
{{- end }}

{{/*
Effective configuration for one service: `defaults` deep-merged with the
per-service entry. Returns YAML; callers use `fromYaml`.
*/}}
{{- define "golden.serviceConfig" -}}
{{- $cfg := mergeOverwrite (deepCopy .root.Values.defaults) (deepCopy (.cfg | default dict)) -}}
{{- if not $cfg.port -}}
{{- fail (printf "services.%s.port is required" .name) -}}
{{- end -}}
{{- toYaml $cfg -}}
{{- end }}

{{- define "golden.image" -}}
{{- $repo := .Values.image.repository -}}
{{- if not $repo -}}
{{- $repo = printf "%s/%s" (trimSuffix "/" (required "image.registry is required" .Values.image.registry)) .Values.image.name -}}
{{- end -}}
{{- printf "%s:%s" $repo (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{- define "golden.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "golden.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "golden.apiKeysSecretName" -}}
{{- default (printf "%s-api-keys" (include "golden.fullname" .)) .Values.apiKeys.existingSecret }}
{{- end }}

{{- define "golden.configMapName" -}}
{{- printf "%s-config" (include "golden.fullname" .) }}
{{- end }}
