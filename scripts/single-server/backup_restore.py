#!/usr/bin/env python3
"""Authoritative single-server backup and restore tooling.

The backup contract intentionally covers PostgreSQL and the MinIO
``raw-documents`` bucket. Kafka, Neo4j, OpenSearch, Valkey, Prometheus, and
Grafana are recorded in the inventory but are not represented as restorable
backup data by this command. They remain derived, transient, or operational
stores and must be rebuilt or reconfigured during a recovery drill.

Runtime Secret values are never exported. The operator must retain the
0600-protected runtime environment file separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Sequence

BACKUP_FORMAT = "signalchord-single-server-backup/v1"
UTILITY_POD = "signalchord-minio-maintenance"
APP_DEPLOYMENT_PREFIX = "signalchord-"
REQUIRED_FILES = ("postgres.dump", "raw-documents.tar.gz", "cluster-inventory.yaml")


class RecoveryError(RuntimeError):
    pass


@dataclass
class CommandRunner:
    namespace: str

    def run(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        stdout: BinaryIO | int | None = subprocess.PIPE,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            list(args),
            input=input_bytes,
            stdout=stdout,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RecoveryError(f"command failed ({completed.returncode}): {' '.join(args)}\n{stderr}")
        return completed

    def kubectl(
        self,
        *args: str,
        input_bytes: bytes | None = None,
        stdout: BinaryIO | int | None = subprocess.PIPE,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        return self.run(
            ["kubectl", "--namespace", self.namespace, *args],
            input_bytes=input_bytes,
            stdout=stdout,
            check=check,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def parse_json(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"invalid JSON returned by Kubernetes: {exc}") from exc
    if not isinstance(value, dict):
        raise RecoveryError("expected a JSON object from Kubernetes")
    return value


def app_state_from_deployments(payload: dict[str, Any]) -> dict[str, int]:
    state: dict[str, int] = {}
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        name = str(metadata.get("name", ""))
        if name.startswith(APP_DEPLOYMENT_PREFIX):
            replicas = int(item.get("spec", {}).get("replicas", 1) or 0)
            state[name] = replicas
    if not state:
        raise RecoveryError("no SignalChord application Deployments were found")
    return state


def maintenance_pod_manifest(namespace: str, image: str) -> bytes:
    if "@sha256:" not in image:
        raise RecoveryError("the MinIO maintenance image must be pinned by sha256 digest")
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": UTILITY_POD,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": "minio-maintenance",
                "app.kubernetes.io/part-of": "signalchord-maintenance",
            },
        },
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "fsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "mc",
                    "image": image,
                    "command": ["sh", "-c", "sleep 86400"],
                    "env": [
                        {
                            "name": "MINIO_ACCESS_KEY",
                            "valueFrom": {
                                "secretKeyRef": {"name": "signalchord-runtime", "key": "MINIO_ACCESS_KEY"}
                            },
                        },
                        {
                            "name": "MINIO_SECRET_KEY",
                            "valueFrom": {
                                "secretKeyRef": {"name": "signalchord-runtime", "key": "MINIO_SECRET_KEY"}
                            },
                        },
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {"cpu": "25m", "memory": "64Mi", "ephemeral-storage": "1Gi"},
                        "limits": {"cpu": "500m", "memory": "512Mi", "ephemeral-storage": "64Gi"},
                    },
                    "volumeMounts": [
                        {"name": "backup", "mountPath": "/backup"},
                        {"name": "tmp", "mountPath": "/tmp"},
                    ],
                }
            ],
            "volumes": [{"name": "backup", "emptyDir": {}}, {"name": "tmp", "emptyDir": {}}],
        },
    }
    return json.dumps(manifest, separators=(",", ":")).encode("utf-8")


def require_tools(*tools: str) -> None:
    missing = [tool for tool in tools if subprocess.run(["sh", "-c", f"command -v {tool}"], check=False).returncode]
    if missing:
        raise RecoveryError(f"required tools are missing: {', '.join(missing)}")


def current_app_state(runner: CommandRunner) -> dict[str, int]:
    payload = parse_json(
        runner.kubectl(
            "get",
            "deployment",
            "--selector",
            "app.kubernetes.io/part-of=signalchord",
            "--output",
            "json",
        ).stdout
    )
    return app_state_from_deployments(payload)


def current_cron_suspend(runner: CommandRunner) -> bool | None:
    result = runner.kubectl("get", "cronjob", "signalchord-feed-collector", "--output", "json", check=False)
    if result.returncode != 0:
        return None
    return bool(parse_json(result.stdout).get("spec", {}).get("suspend", False))


def pause_writers(runner: CommandRunner, state: dict[str, int], cron_suspend: bool | None) -> None:
    if cron_suspend is not None:
        runner.kubectl(
            "patch",
            "cronjob",
            "signalchord-feed-collector",
            "--type=merge",
            "--patch",
            '{"spec":{"suspend":true}}',
        )
    for name in sorted(state):
        runner.kubectl("scale", "deployment", name, "--replicas=0")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        payload = parse_json(
            runner.kubectl(
                "get",
                "deployment",
                "--selector",
                "app.kubernetes.io/part-of=signalchord",
                "--output",
                "json",
            ).stdout
        )
        ready = {
            str(item.get("metadata", {}).get("name", "")): int(item.get("status", {}).get("readyReplicas", 0) or 0)
            for item in payload.get("items", [])
            if str(item.get("metadata", {}).get("name", "")).startswith(APP_DEPLOYMENT_PREFIX)
        }
        if ready and all(value == 0 for value in ready.values()):
            return
        time.sleep(2)
    raise RecoveryError("application Deployments did not reach zero ready replicas within five minutes")


def resume_writers(runner: CommandRunner, state: dict[str, int], cron_suspend: bool | None) -> None:
    errors: list[str] = []
    for name, replicas in sorted(state.items()):
        try:
            runner.kubectl("scale", "deployment", name, f"--replicas={replicas}")
        except RecoveryError as exc:
            errors.append(str(exc))
    if cron_suspend is not None:
        try:
            runner.kubectl(
                "patch",
                "cronjob",
                "signalchord-feed-collector",
                "--type=merge",
                "--patch",
                json.dumps({"spec": {"suspend": cron_suspend}}),
            )
        except RecoveryError as exc:
            errors.append(str(exc))
    if errors:
        raise RecoveryError("failed to resume application writers:\n" + "\n".join(errors))


def create_maintenance_pod(runner: CommandRunner, image: str) -> None:
    runner.kubectl("delete", "pod", UTILITY_POD, "--ignore-not-found", "--wait=true")
    runner.run(["kubectl", "apply", "--filename", "-"], input_bytes=maintenance_pod_manifest(runner.namespace, image))
    runner.kubectl("wait", "--for=condition=Ready", f"pod/{UTILITY_POD}", "--timeout=180s")
    runner.kubectl(
        "exec",
        UTILITY_POD,
        "--",
        "sh",
        "-ec",
        'mc alias set signalchord http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null',
    )


def delete_maintenance_pod(runner: CommandRunner) -> None:
    runner.kubectl("delete", "pod", UTILITY_POD, "--ignore-not-found", "--wait=true", check=False)


def collect_inventory(runner: CommandRunner, destination: Path) -> None:
    command = [
        "kubectl",
        "--namespace",
        runner.namespace,
        "get",
        "deployment,statefulset,cronjob,service,pvc,ingress,networkpolicy",
        "--output",
        "yaml",
    ]
    with destination.open("wb") as stream:
        runner.run(command, stdout=stream)
    destination.chmod(0o600)


def backup(args: argparse.Namespace) -> int:
    require_tools("kubectl", "helm", "git")
    destination = Path(args.output).expanduser().resolve()
    if destination.exists():
        raise RecoveryError(f"backup destination already exists: {destination}")
    destination.mkdir(parents=True, mode=0o700)
    runner = CommandRunner(args.namespace)
    state = current_app_state(runner)
    cron_suspend = current_cron_suspend(runner)
    paused = False
    utility_created = False
    try:
        pause_writers(runner, state, cron_suspend)
        paused = True

        with (destination / "postgres.dump").open("wb") as stream:
            runner.kubectl(
                "exec",
                "statefulset/postgres",
                "--",
                "sh",
                "-ec",
                'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom',
                stdout=stream,
            )
        (destination / "postgres.dump").chmod(0o600)

        create_maintenance_pod(runner, args.minio_client_image)
        utility_created = True
        runner.kubectl(
            "exec",
            UTILITY_POD,
            "--",
            "sh",
            "-ec",
            "rm -rf /backup/raw-documents && mkdir -p /backup/raw-documents && "
            "mc mirror --overwrite signalchord/raw-documents /backup/raw-documents",
        )
        with (destination / "raw-documents.tar.gz").open("wb") as stream:
            runner.kubectl(
                "exec",
                UTILITY_POD,
                "--",
                "tar",
                "-C",
                "/backup",
                "-czf",
                "-",
                "raw-documents",
                stdout=stream,
            )
        (destination / "raw-documents.tar.gz").chmod(0o600)

        collect_inventory(runner, destination / "cluster-inventory.yaml")
        write_private(destination / "signalchord-values.yaml", runner.run(["helm", "--namespace", args.namespace, "get", "values", "signalchord", "--all"]).stdout)
        write_private(destination / "community-values.yaml", runner.run(["helm", "--namespace", args.namespace, "get", "values", "signalchord-community", "--all"]).stdout)

        git_sha = runner.run(["git", "rev-parse", "HEAD"], check=False).stdout.decode("utf-8", errors="replace").strip()
        manifest = {
            "format": BACKUP_FORMAT,
            "created_at": utc_now(),
            "namespace": args.namespace,
            "git_sha": git_sha or None,
            "maintenance_image": args.minio_client_image,
            "included": {
                "postgresql": "logical custom-format dump",
                "minio_raw_documents": "object-level mirror of raw-documents",
            },
            "not_restored": ["kafka", "neo4j", "opensearch", "valkey", "prometheus", "grafana"],
            "runtime_secret_exported": False,
            "application_replicas": state,
            "feed_collector_original_suspend": cron_suspend,
            "files": {
                path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                for path in sorted(destination.iterdir())
                if path.is_file() and path.name != "manifest.json"
            },
        }
        write_private(destination / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
        print(f"backup completed: {destination}")
        print("runtime Secret values were not exported; retain the protected runtime.env separately")
        return 0
    finally:
        if utility_created:
            delete_maintenance_pod(runner)
        if paused:
            resume_writers(runner, state, cron_suspend)


def load_and_verify_backup(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise RecoveryError("backup manifest.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecoveryError(f"backup manifest is invalid JSON: {exc}") from exc
    if manifest.get("format") != BACKUP_FORMAT:
        raise RecoveryError(f"unsupported backup format: {manifest.get('format')!r}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise RecoveryError("backup manifest has no files map")
    for required in REQUIRED_FILES:
        if required not in files:
            raise RecoveryError(f"backup manifest does not contain {required}")
    for name, metadata in files.items():
        path = directory / name
        if not path.is_file():
            raise RecoveryError(f"backup file is missing: {name}")
        expected = str(metadata.get("sha256", ""))
        actual = sha256_file(path)
        if actual != expected:
            raise RecoveryError(f"backup checksum mismatch for {name}: expected {expected}, got {actual}")
    return manifest


def restore(args: argparse.Namespace) -> int:
    require_tools("kubectl", "helm")
    directory = Path(args.backup).expanduser().resolve()
    if args.confirm_namespace != args.namespace or not args.yes:
        raise RecoveryError("restore requires --yes and --confirm-namespace matching --namespace")
    manifest = load_and_verify_backup(directory)
    if manifest.get("namespace") != args.namespace and not args.allow_cross_namespace:
        raise RecoveryError(
            f"backup namespace {manifest.get('namespace')!r} does not match {args.namespace!r}; "
            "use --allow-cross-namespace only for a reviewed recovery drill"
        )

    runner = CommandRunner(args.namespace)
    state = current_app_state(runner)
    cron_suspend = current_cron_suspend(runner)
    paused = False
    utility_created = False
    report: dict[str, Any] = {
        "format": "signalchord-single-server-restore-report/v1",
        "started_at": utc_now(),
        "namespace": args.namespace,
        "backup": str(directory),
        "backup_created_at": manifest.get("created_at"),
        "status": "started",
    }
    try:
        pause_writers(runner, state, cron_suspend)
        paused = True

        with (directory / "postgres.dump").open("rb") as stream:
            runner.kubectl(
                "exec",
                "--stdin",
                "statefulset/postgres",
                "--",
                "sh",
                "-ec",
                'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --clean --if-exists --no-owner '
                '-U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                input_bytes=stream.read(),
            )

        create_maintenance_pod(runner, args.minio_client_image)
        utility_created = True
        runner.kubectl("exec", UTILITY_POD, "--", "mkdir", "-p", "/backup")
        with (directory / "raw-documents.tar.gz").open("rb") as stream:
            runner.kubectl(
                "exec",
                "--stdin",
                UTILITY_POD,
                "--",
                "tar",
                "-C",
                "/backup",
                "-xzf",
                "-",
                input_bytes=stream.read(),
            )
        runner.kubectl(
            "exec",
            UTILITY_POD,
            "--",
            "sh",
            "-ec",
            "mc rm --recursive --force signalchord/raw-documents >/dev/null 2>&1 || true; "
            "mc mb --ignore-existing signalchord/raw-documents >/dev/null; "
            "mc mirror --overwrite --remove /backup/raw-documents signalchord/raw-documents",
        )

        report["status"] = "restored"
        report["completed_at"] = utc_now()
        report["not_restored"] = manifest.get("not_restored", [])
        report_path = Path(args.report).expanduser().resolve() if args.report else directory / "restore-report.json"
        write_private(report_path, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        print(f"authoritative restore completed; report: {report_path}")
        print("derived stores were not restored; run Kubernetes acceptance and the synthetic canary before use")
        return 0
    except Exception:
        report["status"] = "failed"
        report["completed_at"] = utc_now()
        report_path = Path(args.report).expanduser().resolve() if args.report else directory / "restore-report.json"
        write_private(report_path, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        raise
    finally:
        if utility_created:
            delete_maintenance_pod(runner)
        if paused:
            resume_writers(runner, state, cron_suspend)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="create an authoritative PostgreSQL and MinIO backup")
    backup_parser.add_argument("--namespace", default="signalchord")
    backup_parser.add_argument("--output", required=True)
    backup_parser.add_argument("--minio-client-image", required=True, help="exact minio/mc image@sha256 digest")
    backup_parser.set_defaults(handler=backup)

    restore_parser = subparsers.add_parser("restore", help="destructively restore PostgreSQL and MinIO")
    restore_parser.add_argument("--namespace", default="signalchord")
    restore_parser.add_argument("--backup", required=True)
    restore_parser.add_argument("--minio-client-image", required=True, help="exact minio/mc image@sha256 digest")
    restore_parser.add_argument("--confirm-namespace", required=True)
    restore_parser.add_argument("--allow-cross-namespace", action="store_true")
    restore_parser.add_argument("--report")
    restore_parser.add_argument("--yes", action="store_true")
    restore_parser.set_defaults(handler=restore)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except RecoveryError as exc:
        print(f"recovery error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
