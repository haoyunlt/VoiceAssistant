{{/*
Expand the name of the chart.
*/}}
{{- define "voiceassistant.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "voiceassistant.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "voiceassistant.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "voiceassistant.labels" -}}
helm.sh/chart: {{ include "voiceassistant.chart" . }}
{{ include "voiceassistant.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "voiceassistant.selectorLabels" -}}
app.kubernetes.io/name: {{ include "voiceassistant.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "voiceassistant.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "voiceassistant.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image registry
*/}}
{{- define "voiceassistant.imageRegistry" -}}
{{- if .Values.global.imageRegistry }}
{{- .Values.global.imageRegistry }}
{{- else }}
{{- .Values.imageRegistry }}
{{- end }}
{{- end }}

{{/*
Common service template
*/}}
{{- define "voiceassistant.service.template" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ .name }}
  namespace: {{ .namespace }}
  labels:
    app: {{ .name }}
    {{- if .labels }}
    {{- toYaml .labels | nindent 4 }}
    {{- end }}
spec:
  type: {{ .serviceType | default "ClusterIP" }}
  selector:
    app: {{ .name }}
  ports:
  {{- range .ports }}
  - port: {{ .port }}
    targetPort: {{ .targetPort }}
    protocol: {{ .protocol | default "TCP" }}
    name: {{ .name }}
  {{- end }}
{{- end }}

{{/*
Common deployment template
*/}}
{{- define "voiceassistant.deployment.template" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
  namespace: {{ .namespace }}
  labels:
    app: {{ .name }}
    version: {{ .version | default "v1" }}
    {{- if .labels }}
    {{- toYaml .labels | nindent 4 }}
    {{- end }}
spec:
  replicas: {{ .replicas | default 1 }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: {{ .name }}
      version: {{ .version | default "v1" }}
  template:
    metadata:
      labels:
        app: {{ .name }}
        version: {{ .version | default "v1" }}
        {{- if .podLabels }}
        {{- toYaml .podLabels | nindent 8 }}
        {{- end }}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: {{ .metricsPort | default "9090" | quote }}
        sidecar.istio.io/inject: "true"
        {{- if .podAnnotations }}
        {{- toYaml .podAnnotations | nindent 8 }}
        {{- end }}
    spec:
      serviceAccountName: {{ .serviceAccount | default "default" }}
      {{- if .securityContext }}
      securityContext:
        {{- toYaml .securityContext | nindent 8 }}
      {{- end }}
      {{- if .initContainers }}
      initContainers:
      {{- toYaml .initContainers | nindent 6 }}
      {{- end }}
      containers:
      - name: {{ .name }}
        image: {{ .image }}
        imagePullPolicy: {{ .imagePullPolicy | default "IfNotPresent" }}
        {{- if .ports }}
        ports:
        {{- range .ports }}
        - containerPort: {{ .containerPort }}
          name: {{ .name }}
          protocol: {{ .protocol | default "TCP" }}
        {{- end }}
        {{- end }}
        {{- if .envFrom }}
        envFrom:
        {{- toYaml .envFrom | nindent 8 }}
        {{- end }}
        {{- if .env }}
        env:
        {{- toYaml .env | nindent 8 }}
        {{- end }}
        {{- if .livenessProbe }}
        livenessProbe:
          {{- toYaml .livenessProbe | nindent 10 }}
        {{- end }}
        {{- if .readinessProbe }}
        readinessProbe:
          {{- toYaml .readinessProbe | nindent 10 }}
        {{- end }}
        {{- if .resources }}
        resources:
          {{- toYaml .resources | nindent 10 }}
        {{- end }}
        {{- if .volumeMounts }}
        volumeMounts:
        {{- toYaml .volumeMounts | nindent 8 }}
        {{- end }}
      {{- if .volumes }}
      volumes:
      {{- toYaml .volumes | nindent 6 }}
      {{- end }}
      terminationGracePeriodSeconds: {{ .terminationGracePeriodSeconds | default 30 }}
{{- end }}

{{/*
Create HPA template
*/}}
{{- define "voiceassistant.hpa.template" -}}
{{- if .enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .name }}-hpa
  namespace: {{ .namespace }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .name }}
  minReplicas: {{ .minReplicas | default 1 }}
  maxReplicas: {{ .maxReplicas | default 10 }}
  metrics:
  {{- if .targetCPUUtilizationPercentage }}
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ .targetCPUUtilizationPercentage }}
  {{- end }}
  {{- if .targetMemoryUtilizationPercentage }}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: {{ .targetMemoryUtilizationPercentage }}
  {{- end }}
  {{- if .behavior }}
  behavior:
    {{- toYaml .behavior | nindent 4 }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Create PDB template
*/}}
{{- define "voiceassistant.pdb.template" -}}
{{- if .enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ .name }}-pdb
  namespace: {{ .namespace }}
spec:
  {{- if .minAvailable }}
  minAvailable: {{ .minAvailable }}
  {{- else if .maxUnavailable }}
  maxUnavailable: {{ .maxUnavailable }}
  {{- end }}
  selector:
    matchLabels:
      app: {{ .name }}
{{- end }}
{{- end }}
