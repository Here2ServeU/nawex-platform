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

{{/*
Pod template shared by the Deployment and the Argo Rollout of one service.
Usage: include "golden.podTemplate" (dict "root" $ "name" $name "cfg" $raw "svc" $svc)
Output starts at `metadata:` (indent with nindent).
*/}}
{{- define "golden.podTemplate" -}}
{{- $root := .root }}
{{- $name := .name }}
{{- $svc := .svc }}
{{- $ctx := dict "root" $root "name" $name }}
{{- $gpu := deepCopy ($svc.gpu | default dict) }}
{{- if and $root.Values.gpu.enabled (hasKey $gpu "resourceName") }}
{{- $_ := set $gpu "enabled" true }}
{{- end }}
{{- $resources := deepCopy ($svc.resources | default dict) }}
{{- $nodeSelector := deepCopy ($svc.nodeSelector | default dict) }}
{{- $tolerations := $svc.tolerations | default list }}
{{- if $gpu.enabled }}
{{- $limits := $resources.limits | default dict }}
{{- $_ := set $limits ($gpu.resourceName | default "nvidia.com/gpu") (int ($gpu.count | default 1)) }}
{{- $_ := set $resources "limits" $limits }}
{{- $nodeSelector = mergeOverwrite $nodeSelector ($gpu.nodeSelector | default dict) }}
{{- $tolerations = concat $tolerations ($gpu.tolerations | default list) }}
{{- end -}}
metadata:
  labels:
    {{- include "golden.selectorLabels" $ctx | nindent 4 }}
    app.kubernetes.io/part-of: golden
    app.kubernetes.io/component: {{ $name }}
    {{- with $root.Values.podLabels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
    {{- with $svc.podLabels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
  annotations:
    checksum/config: {{ include (print $root.Template.BasePath "/configmap.yaml") $root | sha256sum }}
    {{- if $root.Values.metrics.podAnnotations }}
    prometheus.io/scrape: "true"
    prometheus.io/port: {{ $svc.port | quote }}
    prometheus.io/path: {{ $root.Values.metrics.path | quote }}
    {{- end }}
    {{- with $root.Values.podAnnotations }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
    {{- with $svc.podAnnotations }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
spec:
  serviceAccountName: {{ include "golden.serviceAccountName" $root }}
  automountServiceAccountToken: {{ $root.Values.serviceAccount.automountServiceAccountToken }}
  {{- with $root.Values.imagePullSecrets }}
  imagePullSecrets:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $svc.priorityClassName }}
  priorityClassName: {{ . }}
  {{- end }}
  {{- if and $gpu.enabled $gpu.runtimeClassName }}
  runtimeClassName: {{ $gpu.runtimeClassName }}
  {{- end }}
  terminationGracePeriodSeconds: {{ $svc.terminationGracePeriodSeconds }}
  securityContext:
    {{- toYaml $root.Values.podSecurityContext | nindent 4 }}
  containers:
    - name: {{ $name }}
      image: {{ include "golden.image" $root | quote }}
      imagePullPolicy: {{ $root.Values.image.pullPolicy }}
      command: ["golden", "serve", {{ $name | quote }}]
      ports:
        - name: http
          containerPort: {{ $svc.port }}
          protocol: TCP
      env:
        - name: GOLDEN_SERVICE
          value: {{ $name | quote }}
        - name: GOLDEN_PORT
          value: {{ $svc.port | quote }}
        - name: GOLDEN_API_KEYS
          valueFrom:
            secretKeyRef:
              name: {{ include "golden.apiKeysSecretName" $root }}
              key: {{ $root.Values.apiKeys.secretKey }}
              optional: {{ $root.Values.apiKeys.optional }}
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        {{- range $k, $v := $svc.env }}
        - name: {{ $k }}
          value: {{ $v | quote }}
        {{- end }}
      envFrom:
        - configMapRef:
            name: {{ include "golden.configMapName" $root }}
      {{- with $svc.livenessProbe }}
      livenessProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with $svc.readinessProbe }}
      readinessProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with $svc.startupProbe }}
      startupProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      resources:
        {{- toYaml $resources | nindent 8 }}
      securityContext:
        {{- toYaml $root.Values.containerSecurityContext | nindent 8 }}
      volumeMounts:
        - name: tmp
          mountPath: /tmp
        {{- if $svc.persistence.enabled }}
        - name: data
          mountPath: {{ $svc.persistence.mountPath }}
        {{- end }}
  volumes:
    - name: tmp
      emptyDir:
        sizeLimit: {{ $root.Values.tmpVolume.sizeLimit }}
    {{- if $svc.persistence.enabled }}
    - name: data
      persistentVolumeClaim:
        claimName: {{ include "golden.serviceName" $ctx }}-data
    {{- end }}
  {{- with $nodeSelector }}
  nodeSelector:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $tolerations }}
  tolerations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $svc.affinity }}
  affinity:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $svc.topologySpreadConstraints }}
  topologySpreadConstraints:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}

{{/*
"true" when this service renders an Argo Rollout instead of a Deployment
(global rollouts.enabled AND services.<name>.rollout.enabled).
Usage: include "golden.isRollout" (dict "root" $ "svc" $svc)
*/}}
{{- define "golden.isRollout" -}}
{{- if and .root.Values.rollouts.enabled .svc.rollout .svc.rollout.enabled -}}
true
{{- end -}}
{{- end }}

{{/*
"true" when KEDA scales this service (a ScaledObject replaces the HPA).
*/}}
{{- define "golden.isKeda" -}}
{{- if and .svc.keda .svc.keda.enabled -}}
true
{{- end -}}
{{- end }}

{{/*
scaleTargetRef body (apiVersion/kind/name) for the workload of one service.
Usage: include "golden.scaleTargetRef" (dict "root" $ "name" $name "svc" $svc)
*/}}
{{- define "golden.scaleTargetRef" -}}
{{- if include "golden.isRollout" . -}}
apiVersion: argoproj.io/v1alpha1
kind: Rollout
{{- else -}}
apiVersion: apps/v1
kind: Deployment
{{- end }}
name: {{ include "golden.serviceName" . }}
{{- end }}

{{/*
PromQL label matchers selecting one service's request metrics. Matches both
pod-annotation scraping (service=<name>, set by the app) and Prometheus
Operator scraping (service=<k8s Service name>; the app label becomes
exported_service).
*/}}
{{- define "golden.promSelector" -}}
{{- printf "namespace=\"%s\",service=~\"%s|%s\",path!~\"/health|/ready|/metrics\"" .root.Release.Namespace .name (include "golden.serviceName" .) -}}
{{- end }}
