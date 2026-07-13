{{- define "signalchord.name" -}}signalchord{{- end -}}
{{- define "signalchord.serviceAccountName" -}}{{ default "signalchord" .Values.serviceAccount.name }}{{- end -}}
