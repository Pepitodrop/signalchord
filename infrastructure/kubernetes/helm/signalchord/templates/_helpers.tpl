{{- define "signalchord.name" -}}signalchord{{- end -}}
{{- define "signalchord.serviceAccountName" -}}{{ default "signalchord" .Values.serviceAccount.name }}{{- end -}}
{{- define "signalchord.workloadServiceAccountName" -}}{{ printf "%s-%s" (include "signalchord.serviceAccountName" .root) .name | trunc 63 | trimSuffix "-" }}{{- end -}}
