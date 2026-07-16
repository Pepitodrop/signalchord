#!/usr/bin/env sh
set -eu

umask 077
NAMESPACE=signalchord
OUTPUT=
RUNTIME_ENV=
AGE_RECIPIENT=
CONFIRM=false
MINIO_POD=
MINIO_REPLICAS=
NEO4J_POD=
NEO4J_REPLICAS=
DEPLOYMENT_REPLICAS=
FEED_COLLECTOR_SUSPEND=
APPLICATION_QUIESCED=false
STAGING=

usage() {
  echo "usage: $0 --output DIR --runtime-env FILE --age-recipient RECIPIENT [--namespace NAME] --yes" >&2
}

restore_application() {
  if [ "$APPLICATION_QUIESCED" != true ]; then
    return
  fi
  if [ -n "$DEPLOYMENT_REPLICAS" ] && [ -f "$DEPLOYMENT_REPLICAS" ]; then
    while IFS=' ' read -r deployment replicas; do
      [ -n "$deployment" ] || continue
      kubectl -n "$NAMESPACE" scale "deployment/$deployment" --replicas "$replicas" >/dev/null 2>&1 || true
    done < "$DEPLOYMENT_REPLICAS"
  fi
  case "$FEED_COLLECTOR_SUSPEND" in
    true) suspend_patch='{"spec":{"suspend":true}}' ;;
    *) suspend_patch='{"spec":{"suspend":false}}' ;;
  esac
  kubectl -n "$NAMESPACE" patch cronjob signalchord-feed-collector --type merge -p "$suspend_patch" >/dev/null 2>&1 || true
  APPLICATION_QUIESCED=false
}

cleanup() {
  status=$?
  if [ -n "$MINIO_POD" ]; then
    kubectl -n "$NAMESPACE" delete pod "$MINIO_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
  if [ -n "$NEO4J_POD" ]; then
    kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
  if [ -n "$MINIO_REPLICAS" ]; then
    kubectl -n "$NAMESPACE" scale statefulset/minio --replicas "$MINIO_REPLICAS" >/dev/null 2>&1 || true
  fi
  if [ -n "$NEO4J_REPLICAS" ]; then
    kubectl -n "$NAMESPACE" scale statefulset/neo4j --replicas "$NEO4J_REPLICAS" >/dev/null 2>&1 || true
  fi
  restore_application
  if [ -n "$DEPLOYMENT_REPLICAS" ]; then rm -f "$DEPLOYMENT_REPLICAS"; fi
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

DEPLOYMENT_REPLICAS=$(mktemp "${TMPDIR:-/tmp}/signalchord-backup-replicas.XXXXXX")
kubectl -n "$NAMESPACE" get deployments -l app.kubernetes.io/part-of=signalchord \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.replicas}{"\n"}{end}' > "$DEPLOYMENT_REPLICAS"
FEED_COLLECTOR_SUSPEND=$(kubectl -n "$NAMESPACE" get cronjob signalchord-feed-collector -o jsonpath='{.spec.suspend}')
[ -n "$FEED_COLLECTOR_SUSPEND" ] || FEED_COLLECTOR_SUSPEND=false
APPLICATION_QUIESCED=true
kubectl -n "$NAMESPACE" patch cronjob signalchord-feed-collector --type merge -p '{"spec":{"suspend":true}}' >/dev/null
for job in $(kubectl -n "$NAMESPACE" get jobs -l app.kubernetes.io/name=feed-collector -o name); do
  kubectl -n "$NAMESPACE" wait --for=condition=complete "$job" --timeout=10m >/dev/null
 done
kubectl -n "$NAMESPACE" scale deployments -l app.kubernetes.io/part-of=signalchord --replicas 0 >/dev/null
while IFS=' ' read -r deployment _; do
  [ -n "$deployment" ] || continue
  kubectl -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout=10m >/dev/null
done < "$DEPLOYMENT_REPLICAS"

# The variables below are expanded by the shell inside the PostgreSQL container.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec statefulset/postgres -- sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=9 --no-owner --no-acl' \
  > "$STAGING/data/postgres.dump"

postgres_image=$(kubectl -n "$NAMESPACE" get statefulset postgres -o jsonpath='{.spec.template.spec.containers[0].image}')
MINIO_REPLICAS=$(kubectl -n "$NAMESPACE" get statefulset minio -o jsonpath='{.spec.replicas}')
MINIO_POD="signalchord-minio-backup-$(date +%s)"
kubectl -n "$NAMESPACE" scale statefulset/minio --replicas 0 >/dev/null
kubectl -n "$NAMESPACE" rollout status statefulset/minio --timeout=10m >/dev/null
cat <<EOF_POD | kubectl -n "$NAMESPACE" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: $MINIO_POD
  labels:
    app.kubernetes.io/name: minio-backup
    app.kubernetes.io/part-of: signalchord
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 999
    runAsGroup: 999
    fsGroup: 1000
    seccompProfile: {type: RuntimeDefault}
  containers:
    - name: backup
      image: $postgres_image
      command: [sh, -c, 'sleep 3600']
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: {drop: [ALL]}
      volumeMounts:
        - {name: data, mountPath: /data}
  volumes:
    - name: data
      persistentVolumeClaim: {claimName: data-minio-0}
EOF_POD
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$MINIO_POD" --timeout=5m >/dev/null
kubectl -n "$NAMESPACE" exec "$MINIO_POD" -- tar -C /data -cf - . > "$STAGING/data/minio.tar"
kubectl -n "$NAMESPACE" delete pod "$MINIO_POD" --wait=true >/dev/null
MINIO_POD=
kubectl -n "$NAMESPACE" scale statefulset/minio --replicas "$MINIO_REPLICAS" >/dev/null
kubectl -n "$NAMESPACE" rollout status statefulset/minio --timeout=10m >/dev/null
MINIO_REPLICAS=

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
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- neo4j-admin database dump system --to-path=/backup --overwrite-destination=true
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- cat /backup/neo4j.dump > "$STAGING/data/neo4j.dump"
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- cat /backup/system.dump > "$STAGING/data/neo4j-system.dump"
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
        "authoritative": ["postgresql", "neo4j", "neo4j-system", "minio", "runtime-config"],
        "rebuild_only": ["kafka", "opensearch", "valkey"],
        "application_quiesced": True,
    }, handle, indent=2)
    handle.write("\n")
PY
(
  cd "$STAGING"
  checksum_tmp=$(mktemp "${TMPDIR:-/tmp}/signalchord-checksums.XXXXXX")
  find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r file; do
    sha256sum "${file#./}"
  done > "$checksum_tmp"
  mv "$checksum_tmp" SHA256SUMS
)

restore_application
rm -f "$DEPLOYMENT_REPLICAS"
DEPLOYMENT_REPLICAS=
mkdir -p "$(dirname "$OUTPUT")"
mv "$STAGING" "$OUTPUT"
STAGING=
chmod -R go-rwx "$OUTPUT"
echo "SignalChord backup completed: $OUTPUT"
echo "Test restoration before relying on this backup. Kafka, OpenSearch and Valkey are rebuilt from authoritative data."
