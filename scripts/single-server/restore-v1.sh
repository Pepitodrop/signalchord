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
PATCHED_RUNTIME=
SUCCESS=false
POSTGRES_ONLY=false
CONFIRM_CONTEXT=
SMTP_BLACKHOLE_HOST=
EXPO_BLACKHOLE_URL=

RESTORE_TARGET_ANNOTATION='signalchord.io/restore-target'

usage() {
  echo "usage: $0 --backup DIR --host HOST (--runtime-env FILE | --age-identity FILE) \\
       --confirm-context NAME --smtp-blackhole-host HOST --expo-blackhole-url URL \\
       [--namespace NAME] [--postgres-only] [--insecure] --yes" >&2
}

cleanup() {
  status=$?
  [ -z "$MINIO_POD" ] || kubectl -n "$NAMESPACE" delete pod "$MINIO_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  [ -z "$NEO4J_POD" ] || kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  [ -z "$DEPLOYMENT_REPLICAS" ] || rm -f "$DEPLOYMENT_REPLICAS"
  [ -z "$DECRYPTED_RUNTIME" ] || rm -f "$DECRYPTED_RUNTIME"
  [ -z "$PATCHED_RUNTIME" ] || rm -f "$PATCHED_RUNTIME"
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
    --postgres-only) POSTGRES_ONLY=true; shift ;;
    --confirm-context) CONFIRM_CONTEXT=$2; shift 2 ;;
    --smtp-blackhole-host) SMTP_BLACKHOLE_HOST=$2; shift 2 ;;
    --expo-blackhole-url) EXPO_BLACKHOLE_URL=$2; shift 2 ;;
    --insecure) INSECURE=true; shift ;;
    --yes) CONFIRM=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [ -z "$BACKUP" ] || [ -z "$HOST" ] || [ "$CONFIRM" != true ] \
  || [ -z "$CONFIRM_CONTEXT" ] || [ -z "$SMTP_BLACKHOLE_HOST" ] || [ -z "$EXPO_BLACKHOLE_URL" ]; then
  usage
  exit 2
fi
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
if [ "$POSTGRES_ONLY" = true ]; then
  required_artifacts="manifest.json data/postgres.dump runtime.env.age"
else
  required_artifacts="manifest.json data/postgres.dump data/minio.tar data/neo4j.dump data/neo4j-system.dump runtime.env.age"
fi
for required in $required_artifacts; do
  [ -f "$BACKUP/$required" ] || { echo "required backup artifact missing: $required" >&2; exit 1; }
done
python3 - "$BACKUP/manifest.json" "$POSTGRES_ONLY" <<'PY'
import json, sys
path, postgres_only = sys.argv[1], sys.argv[2] == "true"
with open(path, encoding="utf-8") as handle:
    manifest = json.load(handle)
if postgres_only:
    if manifest.get("format") != "signalchord-single-server-backup-postgres-only" or manifest.get("version") != 1:
        raise SystemExit("unsupported SignalChord postgres-only backup format")
    required = {"postgresql", "runtime-config"}
    if not required.issubset(set(manifest.get("authoritative", []))):
        raise SystemExit("backup manifest is missing authoritative data sets")
else:
    if manifest.get("format") != "signalchord-single-server-backup" or manifest.get("version") != 1:
        raise SystemExit("unsupported SignalChord backup format")
    required = {"postgresql", "neo4j", "neo4j-system", "minio", "runtime-config"}
    if not required.issubset(set(manifest.get("authoritative", []))):
        raise SystemExit("backup manifest is missing authoritative data sets")
    if manifest.get("application_quiesced") is not True:
        raise SystemExit("backup was not created with application writes quiesced")
PY

if [ -n "$AGE_IDENTITY" ]; then
  [ -f "$AGE_IDENTITY" ] || { echo "age identity not found: $AGE_IDENTITY" >&2; exit 1; }
  DECRYPTED_RUNTIME=$(mktemp "${TMPDIR:-/tmp}/signalchord-runtime.XXXXXX")
  age -d -i "$AGE_IDENTITY" -o "$DECRYPTED_RUNTIME" "$BACKUP/runtime.env.age"
  chmod 600 "$DECRYPTED_RUNTIME"
  RUNTIME_ENV=$DECRYPTED_RUNTIME
fi
[ -f "$RUNTIME_ENV" ] || { echo "runtime env file not found: $RUNTIME_ENV" >&2; exit 1; }
runtime_mode=$(stat -c '%a' "$RUNTIME_ENV" 2>/dev/null || stat -f '%Lp' "$RUNTIME_ENV")
[ "$runtime_mode" = 600 ] || { echo "runtime env file must have mode 0600, got $runtime_mode" >&2; exit 1; }

kubectl get namespace "$NAMESPACE" >/dev/null
helm -n "$NAMESPACE" status signalchord >/dev/null
helm -n "$NAMESPACE" status signalchord-community >/dev/null

# Fail closed: refuse to restore into any namespace that was not deliberately
# marked as an allowed restore target. Does NOT use SIGNALCHORD_ENV/environment,
# which is confirmed mislabeled on real production (see TODOS.md).
restore_target=$(kubectl get namespace "$NAMESPACE" \
  -o jsonpath="{.metadata.annotations.$RESTORE_TARGET_ANNOTATION}" 2>/dev/null || true)
if [ "$restore_target" != allowed ]; then
  echo "refusing to restore: namespace $NAMESPACE is missing annotation $RESTORE_TARGET_ANNOTATION=allowed" >&2
  exit 1
fi

# Retype-to-confirm: the operator (or an automated drill) must independently
# state which cluster context they believe they are targeting.
current_context=$(kubectl config current-context)
if [ "$CONFIRM_CONTEXT" != "$current_context" ]; then
  echo "refusing to restore: --confirm-context '$CONFIRM_CONTEXT' does not match kubectl config current-context '$current_context'" >&2
  exit 1
fi
echo "Confirmed restore target: namespace=$NAMESPACE context=$current_context"

DEPLOYMENT_REPLICAS=$(mktemp "${TMPDIR:-/tmp}/signalchord-replicas.XXXXXX")
kubectl -n "$NAMESPACE" get deployments -l app.kubernetes.io/part-of=signalchord \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.replicas}{"\n"}{end}' > "$DEPLOYMENT_REPLICAS"
kubectl -n "$NAMESPACE" scale deployments -l app.kubernetes.io/part-of=signalchord --replicas 0 >/dev/null
kubectl -n "$NAMESPACE" patch cronjob signalchord-feed-collector --type merge -p '{"spec":{"suspend":true}}' >/dev/null

# Outbound-safety: redirect real customer-facing integrations to black-hole
# endpoints in the restored runtime before the application is ever scaled back
# up, so a restored (e.g. staging drill) environment cannot send real email or
# push notifications.
PATCHED_RUNTIME=$(mktemp "${TMPDIR:-/tmp}/signalchord-runtime-patched.XXXXXX")
chmod 600 "$PATCHED_RUNTIME"
grep -v -E '^(SMTP_HOST|EXPO_PUSH_URL)=' "$RUNTIME_ENV" > "$PATCHED_RUNTIME" || true
printf 'SMTP_HOST=%s\n' "$SMTP_BLACKHOLE_HOST" >> "$PATCHED_RUNTIME"
printf 'EXPO_PUSH_URL=%s\n' "$EXPO_BLACKHOLE_URL" >> "$PATCHED_RUNTIME"

kubectl -n "$NAMESPACE" create secret generic signalchord-runtime \
  --from-env-file="$PATCHED_RUNTIME" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# The variables below are expanded by the shell inside the PostgreSQL container.
# shellcheck disable=SC2016
kubectl -n "$NAMESPACE" exec -i statefulset/postgres -- sh -ec \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl --exit-on-error' \
  < "$BACKUP/data/postgres.dump"

if [ "$POSTGRES_ONLY" != true ]; then
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
kubectl -n "$NAMESPACE" exec "$MINIO_POD" -- sh -ec 'find /data -mindepth 1 -depth -delete'
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
kubectl -n "$NAMESPACE" exec -i "$NEO4J_POD" -- sh -ec 'cat > /backup/system.dump' < "$BACKUP/data/neo4j-system.dump"
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- neo4j-admin database load system --from-path=/backup --overwrite-destination=true
kubectl -n "$NAMESPACE" exec "$NEO4J_POD" -- neo4j-admin database load neo4j --from-path=/backup --overwrite-destination=true
kubectl -n "$NAMESPACE" delete pod "$NEO4J_POD" --wait=true >/dev/null
NEO4J_POD=

kubectl -n "$NAMESPACE" scale statefulset/minio statefulset/neo4j --replicas 1 >/dev/null
fi

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
