#!/usr/bin/env sh
set -eu

umask 077
NAMESPACE=signalchord
OUTPUT=
RUNTIME_ENV=
AGE_RECIPIENT=
CONFIRM=false
NEO4J_POD=
NEO4J_REPLICAS=
STAGING=

usage() {
  echo "usage: $0 --output DIR --runtime-env FILE --age-recipient RECIPIENT [--namespace NAME] --yes" >&2
}

cleanup() {
  status=$?
  if [ -n "$NEO4J_POD" ]; then
    kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
  if [ -n "$NEO4J_REPLICAS" ]; then
    kubectl -n "$NAMESPACE" scale statefulset/neo4j --replicas "$NEO4J_REPLICAS" >/dev/null 2>&1 || true
  fi
  if [ -n "$STAGING" ]; then rm -rf "$STAGING"; fi
  exit "$status"
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) OUTPUT=$2; shift 2 ;;
    --runtime-env) RUNTIME_ENV=$2; shift 2 ;;
    --age-recipient) AGE_RECIPIENT=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$OUTPUT" ] || [ -z "$RUNTIME_ENV" ] || [ -z "$AGE_RECIPIENT" ] || [ "$CONFIRM" != true ]; then
  usage
  exit 2
fi
[ -f "$RUNTIME_ENV" ] || { echo "runtime env file not found: $RUNTIME_ENV" >&2; exit 1; }
[ ! -e "$OUTPUT" ] || { echo "backup output already exists: $OUTPUT" >&2; exit 1; }

for tool in kubectl helm age python3 sha256sum tar; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
runtime_mode=$(stat -c '%a' "$RUNTIME_ENV" 2>/dev/null || stat -f '%Lp' "$RUNTIME_ENV")
[ "$runtime_mode" = 600 ] || { echo "runtime env file must have mode 0600, got $runtime_mode" >&2; exit 1; }

kubectl get namespace "$NAMESPACE" >/dev/null
helm -n "$NAMESPACE" status signalchord >/dev/null
helm -n "$NAMESPACE" status signalchord-community >/dev/null

STAGING=$(mktemp -d "${TMPDIR:-/tmp}/signalchord-backup.XXXXXX")
mkdir -p "$STAGING/metadata" "$STAGING/data"
created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
context=$(kubectl config current-context)

helm -n "$NAMESPACE" get values signalchord --all -o yaml > "$STAGING/metadata/signalchord-values.yaml"
helm -n "$NAMESPACE" get values signalchord-community --all -o yaml > "$STAGING/metadata/community-values.yaml"
helm -n "$NAMESPACE" get manifest signalchord > "$STAGING/metadata/signalchord-manifest.yaml"
helm -n "$NAMESPACE" get manifest signalchord-community > "$STAGING/metadata/community-manifest.yaml"
helm -n "$NAMESPACE" history signalchord -o json > "$STAGING/metadata/signalchord-history.json"
helm -n "$NAMESPACE" history signalchord-community -o json > "$STAGING/metadata/community-history.json"
kubectl -n "$NAMESPACE" get statefulsets,deployments,cronjobs,services,pvc -o yaml > "$STAGING/metadata/kubernetes-resources.yaml"
kubectl -n "$NAMESPACE" get statefulset kafka -o jsonpath='{.spec.template.spec.containers[0].image}' > "$STAGING/metadata/kafka-image.txt"
kubectl -n "$NAMESPACE" exec statefulset/kafka -- /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe > "$STAGING/metadata/kafka-topics.txt"
kubectl -n "$NAMESPACE" exec statefulset/opensearch -- sh -ec 'curl -fsS http://localhost:9200/_cat/indices?h=index,health,status,docs.count,store.size' > "$STAGING/metadata/opensearch-indices.txt"

age -r "$AGE_RECIPIENT" -o "$STAGING/runtime.env.age" "$RUNTIME_ENV"

kubectl -n "$NAMESPACE" exec statefulset/postgres -- sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=9 --no-owner --no-acl' \
  > "$STAGING/data/postgres.dump"

kubectl -n "$NAMESPACE" exec statefulset/minio -- sh -ec 'tar -C /data -cf - .' \
  > "$STAGING/data/minio.tar"

NEO4J_REPLICAS=$(kubectl -n "$NAMESPACE" get statefulset neo4j -o jsonpath='{.spec.replicas}')
neo4j_image=$(kubectl -n "$NAMESPACE" get statefulset neo4j -o jsonpath='{.spec.template.spec.containers[0].image}')
NEO4J_POD="signalchord-neo4j-backup-$(date +%s)"
kubectl -n "$NAMESPACE" scale statefulset/neo4j --replicas 0 >/dev/null
kubectl -n "$NAMESPACE" rollout status statefulset/neo4j --timeout=10m >/dev/null
cat <<EOF_POD | kubectl -n "$NAMESPACE" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: $NEO4J_POD
  labels:
    app.kubernetes.io/name: neo4j-backup
    app.kubernetes.io/part-of: signalchord
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 7474
    runAsGroup: 7474
    fsGroup: 7474
    seccompProfile: {type: RuntimeDefault}
  containers:
    - name: backup
      image: $neo4j_image
      command: [sh, -c, 'sleep 3600']
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: {drop: [ALL]}
      volumeMounts:
        - {name: data, mountPath: /data}
        - {name: backup, mountPath: /backup}
  volumes:
    - name: data
      persistentVolumeClaim: {claimName: data-neo4j-0}
    - name: backup
      emptyDir: {}
EOF_POD
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$NEO4J_POD" --timeout=5m >/dev/null
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- neo4j-admin database dump neo4j --to-path=/backup --overwrite-destination=true
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- cat /backup/neo4j.dump > "$STAGING/data/neo4j.dump"
kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --wait=true >/dev/null
NEO4J_POD=
kubectl -n "$NAMESPACE" scale statefulset/neo4j --replicas "$NEO4J_REPLICAS" >/dev/null
kubectl -n "$NAMESPACE" rollout status statefulset/neo4j --timeout=10m >/dev/null
NEO4J_REPLICAS=

python3 - "$STAGING/manifest.json" "$created_at" "$context" "$NAMESPACE" <<'PY'
import json, sys
path, created_at, context, namespace = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump({
        "format": "signalchord-single-server-backup",
        "version": 1,
        "created_at": created_at,
        "kubernetes_context": context,
        "namespace": namespace,
        "authoritative": ["postgresql", "neo4j", "minio", "runtime-config"],
        "rebuild_only": ["kafka", "opensearch", "valkey"],
    }, handle, indent=2)
    handle.write("\n")
PY
(
  cd "$STAGING"
  find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r file; do
    sha256sum "${file#./}"
  done > SHA256SUMS
)
mkdir -p "$(dirname "$OUTPUT")"
mv "$STAGING" "$OUTPUT"
STAGING=
chmod -R go-rwx "$OUTPUT"
echo "SignalChord backup completed: $OUTPUT"
echo "Test restoration before relying on this backup. Kafka, OpenSearch and Valkey are rebuilt from authoritative data."
