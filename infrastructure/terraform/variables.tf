variable "kubernetes_context" {type = string}
variable "namespace" {type = string, default = "signalchord"}
variable "chart_path" {type = string, default = "../kubernetes/helm/signalchord"}
variable "values_files" {type = list(string), default = []}
variable "runtime_secret_name" {type = string, default = "signalchord-runtime"}
