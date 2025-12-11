{{/*
Expand the name of the chart.
*/}}
{{- define "fear-allah-backend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "fear-allah-backend.fullname" -}}
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

{{/*
Common labels
*/}}
{{- define "fear-allah-backend.labels" -}}
helm.sh/chart: {{ include "fear-allah-backend.name" . }}
{{ include "fear-allah-backend.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fear-allah-backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fear-allah-backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
