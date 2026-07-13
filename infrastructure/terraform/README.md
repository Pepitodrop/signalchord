# Terraform deployment wrapper

This module creates a restricted Kubernetes namespace and deploys the SignalChord Helm chart. It deliberately does not provision a cloud-specific Kafka, Neo4j, database, search or object-storage service because the target cloud and operating model are not yet selected.

Runtime secrets must exist before apply through an external secret manager/CSI workflow; Terraform does not accept secret values as variables to avoid unnecessary plaintext state exposure.

```bash
terraform init
terraform plan -var='kubernetes_context=staging'
terraform apply -var='kubernetes_context=staging'
```
