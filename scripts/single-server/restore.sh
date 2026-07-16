#!/usr/bin/env sh
set -eu

umask 077
NAMESPACE=signalchord
BACKUP=
RUNTIME_ENV=
AGE_IDENTITY=
HOST=
INSECURE=false
CONFIRM=false
MINIO_POD=
NEO4J_POD=
DEPLOYMENT_REPLICAS=
DECRYPTED_RUNTIME=
SUCCESS=false

usage() {
  echo "usage: $0 --backup DIR --host HOST (--runtime-env FILE | --age-identity FILE) [--namespace NAME] [--insecure] --yes" >&2
}

cleanup() {
  status=$?
  [ -z "$MINIO_POD" ] || kubectl -n "$NAMESPACE" delete pod "$MINIO_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  [ -z "$NEO4J_POD" ] || kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  [ -z "$DEPLOYMENT_REPLICAS" ] || rm -f "$DEPLOYMENT_REPLICAS"
  [ -z "$DECRYPTED_RUNTIME" ] || rm -f "$DECRYPTED_RUNTIME"
  if [ "$SUCCESS" != true ] && [ "$status" -ne 0 ]; then
    echo "Restore failed. Application workloads remain stopped; inspect the namespace before scaling them up." >&2
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup) BACKUP=$2; shift 2 ;;
    --runtime-env) RUNTIME_ENV=$2; shift 2 ;;
    --age-identity) AGE_IDENTITY=$2; shift 2 ;;
    --host) HOST=$2; shift 2 ;;
    --namespace) NAMESPACE=$2; shift 2 ;;
    --insecure) INSECURE=true; shift ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$BACKUP" ] || [ -z "$HOST" ] || [ "$CONFIRM" != true ]; then usage; exit 2; fi
if [ -n "$RUNTIME_ENV" ] && [ -n "$AGE_IDENTITY" ]; then echo "choose either --runtime-env or --age-identity" >&2; exit 2; fi
if [ -z "$RUNTIME_ENV" ] && [ -z "$AGE_IDENTITY" ]; then usage; exit 2; fi
[ -d "$BACKUP" ] || { echo "backup directory not found: $BACKUP" >&2; exit 1; }

for tool in kubectl helm python3 sha256sum tar; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
if [ -n "$AGE_IDENTITY" ]; then command -v age >/dev/null 2>&1 || { echo "age is required" >&2; exit 1; }; fi

(
  cd "$BACKUP"
  sha256sum -c SHA256SUMS
)
python3 - "$BACKUP/manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    manifest = json.load(handle)
if manifest.get("format") != "signalchord-single-server-backup" or manifest.get("version") != 1:
    raise SystemExit("unsupported SignalChord backup format")
PY

if [ -n "$AGE_IDENTITY" ]; then
  [ -f "$AGE_IDENTITY" ] || { echo "age identity not found: $AGE_IDENTITY" >&2; exit 1; }
  DECRYPTED_RUNTIME=$(mktemp "${TMPDIR:-/tmp}/signalchord-runtime.XXXXXX")
  age -d -i "$AGE_IDENTITY" -o "$DECRYPTED_RUNTIME" "$BACKUP/runtime.env.age"
  chmod 600 "$DECRYPTED_RUNTIME"
  RUNTIME_ENV=$DECRYPTED_RUNTIME
fi
[ -f "$RUNTIME_ENV" ] || { echo "runtime env file not found: $RUNTIME_ENV" >&2; exit 1; }

kubectl get namespace "$NAMESPACE" >/dev/null
helm -n "$NAMESPACE" status signalchord >/dev/null
helm -n "$NAMESPACE" status signalchord-community >/dev/null

DEPLOYMENT_REPLICAS=$(mktemp "${TMPDIR:-/tmp}/signalchord-replicas.XXXXXX")
kubectl -n "$NAMESPACE" get deployments -l app.kubernetes.io/part-of=signalchord \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.replicas}{"\n"}{end}' > "$DEPLOYMENT_REPLICAS"
kubectl -n "$NAMESPACE" scale deployments -l app.kubernetes.io/part-of=signalchord --replicas 0 >/dev/null
kubectl -n "$NAMESPACE" patch cronjob signalchord-feed-collector --type merge -p '{"spec":{"suspend":true}}' >/dev/null

kubectl -n "$NAMESPACE" create secret generic signalchord-runtime \
  --from-env-file="$RUNTIME_ENV" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# The variables below are expanded by the shell inside the PostgreSQL container.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec -i statefulset/postgres -- sh -ec \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl --exit-on-error' \
  < "$BACKUP/data/postgres.dump"

postgres_image=$(kubectl -n "$NAMESPACE" get statefulset postgres -o jsonpath='{.spec.template.spec.containers[0].image}')
MINIO_POD="signalchord-minio-restore-$(date +%s)"
kubectl -n "$NAMESPACE" scale statefulset/minio --replicas 0 >/dev/null
cat <<EOF_POD | kubectl -n "$NAMESPACE" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: $MINIO_POD
  labels: {app.kubernetes.io/name: minio-restore, app.kubernetes.io/part-of: signalchord}
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext: {runAsNonRoot: true, runAsUser: 999, runAsGroup: 999, fsGroup: 1000, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: restore
      image: $postgres_image
      command: [sh, -c, 'sleep 3600']
      securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}}
      volumeMounts: [{name: data, mountPath: /data}]
  volumes:
    - name: data
      persistentVolumeClaim: {claimName: data-minio-0}
EOF_POD
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$MINIO_POD" --timeout=5m >/dev/null
kubectl -n "$NAMESPACE" exec "$MINIO_POD" -- sh -ec 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +'
kubectl -n "$NAMESPACE" exec -i "$MINIO_POD" -- tar -C /data -xf - < "$BACKUP/data/minio.tar"
kubectl -n "$NAMESPACE" delete pod "$MINIO_POD" --wait=true >/dev/null
MINIO_POD=

neo4j_image=$(kubectl -n "$NAMESPACE" get statefulset neo4j -o jsonpath='{.spec.template.spec.containers[0].image}')
NEO4J_POD="signalchord-neo4j-restore-$(date +%s)"
kubectl -n "$NAMESPACE" scale statefulset/neo4j --replicas 0 >/dev/null
cat <<EOF_POD | kubectl -n "$NAMESPACE" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: $NEO4J_POD
  labels: {app.kubernetes.io/name: neo4j-restore, app.kubernetes.io/part-of: signalchord}
spec:
  restartPolicy: Never
  automountServiceAccountToken: false
  securityContext: {runAsNonRoot: true, runAsUser: 7474, runAsGroup: 7474, fsGroup: 7474, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: restore
      image: $neo4j_image
      command: [sh, -c, 'sleep 3600']
      securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}}
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
kubectl -n "$NAMESPACE" exec -i "$NEO4J_POD" -- sh -ec 'cat > /backup/neo4j.dump' < "$BACKUP/data/neo4j.dump"
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- neo4j-admin database load neo4j --from-path=/backup --overwrite-destination=true
kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --wait=true >/dev/null
NEO4J_POD=

kubectl -n "$NAMESPACE" scale statefulset/minio statefulset/neo4j --replicas 1 >/dev/null
while IFS=' ' read -r deployment replicas; do
  [ -n "$deployment" ] || continue
  kubectl -n "$NAMESPACE" scale "deployment/$deployment" --replicas "$replicas" >/dev/null
done < "$DEPLOYMENT_REPLICAS"
kubectl -n "$NAMESPACE" patch cronjob signalchord-feed-collector --type merge -p '{"spec":{"suspend":false}}' >/dev/null

health_args="--namespace $NAMESPACE --host $HOST"
if [ "$INSECURE" = true ]; then health_args="$health_args --insecure"; fi
# shellcheck disable=SC2086
sh scripts/single-server/health.sh $health_args
SUCCESS=true
echo "SignalChord restore completed. Run acceptance.sh and verify rebuilt Kafka/OpenSearch projections before reopening access."
