{{- define "signalchord.name" -}}signalchord{{- end -}}
{{- define "signalchord.serviceAccountName" -}}{{ default "signalchord" .Values.serviceAccount.name }}{{- end -}}
{{- define "signalchord.workloadServiceAccountName" -}}{{ printf "%s-%s" (include "signalchord.serviceAccountName" .root) .name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "signalchord.imageReference" -}}
{{- $root := .root -}}
{{- $image := .image -}}
{{- $digest := default "" (index $root.Values.global.imageDigests $image) -}}
{{- if and (eq $root.Values.global.environment "production") (not $digest) -}}
{{- fail (printf "global.imageDigests.%s is required for production" $image) -}}
{{- end -}}
{{- if $digest -}}
{{- printf "%s/%s@%s" $root.Values.global.imageRegistry $image $digest -}}
{{- else -}}
{{- printf "%s/%s:%s" $root.Values.global.imageRegistry $image $root.Values.global.imageTag -}}
{{- end -}}
{{- end -}}
