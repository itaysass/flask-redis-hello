{{- define "itaysass-flask.fullname" -}}
{{- printf "%s-%s" .Release.Name "flask" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
