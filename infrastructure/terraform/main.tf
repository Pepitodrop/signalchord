provider "kubernetes" {config_path = "~/.kube/config", config_context = var.kubernetes_context}
provider "helm" {kubernetes {config_path = "~/.kube/config", config_context = var.kubernetes_context}}

resource "kubernetes_namespace_v1" "signalchord" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of" = "signalchord"
      "pod-security.kubernetes.io/enforce" = "restricted"
    }
  }
}

resource "helm_release" "signalchord" {
  name = "signalchord"
  namespace = kubernetes_namespace_v1.signalchord.metadata[0].name
  chart = var.chart_path
  atomic = true
  cleanup_on_fail = true
  dependency_update = true
  lint = true
  values = [for file in var.values_files : file(file)]
  set {name = "global.existingSecret", value = var.runtime_secret_name}
}
