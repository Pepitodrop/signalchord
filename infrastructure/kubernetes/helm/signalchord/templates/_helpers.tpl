{{- define "signalchord.name" -}}signalchord{{- end -}}
{{- define "signalchord.serviceAccountName" -}}{{ default "signalchord" .Values.serviceAccount.name }}{{- end -}}
{{- define "signalchord.workloadServiceAccountName" -}}{{ printf "%s-%s" (include "signalchord.serviceAccountName" .root) .name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "signalchord.imageReference" -}}
{{- $root := .root -}}
{{- $image := .image -}}
{{- $digests := default (dict) $root.Values.global.imageDigests -}}
{{- $digest := default "" (index $digests $image) -}}
{{- if and (eq $root.Values.global.environment "production") (not $digest) -}}
{{- fail (printf "global.imageDigests.%s is required for production" $image) -}}
{{- end -}}
{{- if and $digest (not (regexMatch "^sha256:[0-9a-f]{64}$" $digest)) -}}
{{- fail (printf "global.imageDigests.%s must match sha256:<64 lowercase hex characters>" $image) -}}
{{- end -}}
{{- if $digest -}}
{{- printf "%s/%s@%s" $root.Values.global.imageRegistry $image $digest -}}
{{- else -}}
{{- printf "%s/%s:%s" $root.Values.global.imageRegistry $image $root.Values.global.imageTag -}}
{{- end -}}
{{- end -}}
