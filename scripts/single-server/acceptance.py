#!/usr/bin/env python3
"""Validate a deployed single-server cluster and optionally run a synthetic canary."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

REQUIRED_STATEFULSETS = {
    "kafka",
    "postgres",
    "neo4j",
    "valkey",
    "minio",
    "opensearch",
}
REQUIRED_NETWORK_POLICIES = {
    "signalchord-default-deny",
    "signalchord-internal",
    "signalchord-dns-and-dependencies",
    "signalchord-ingress-controller",
}


class AcceptanceError(RuntimeError):
    pass


@dataclass
class Runner:
    namespace: str

    def run(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            list(args),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise AcceptanceError(f"command failed ({completed.returncode}): {' '.join(args)}\n{stderr}")
        return completed

    def kubectl(self, *args: str, input_bytes: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        return self.run(
            ["kubectl", "--namespace", self.namespace, *args],
            input_bytes=input_bytes,
            check=check,
        )

    def json(self, *args: str) -> dict[str, Any]:
        payload = self.kubectl(*args, "--output", "json").stdout
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceError(f"kubectl returned invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise AcceptanceError("kubectl JSON result was not an object")
        return value


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def item_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("metadata", {}).get("name", "")): item
        for item in payload.get("items", [])
        if item.get("metadata", {}).get("name")
    }


def validate_namespace(runner: Runner) -> None:
    namespace = runner.run(["kubectl", "get", "namespace", runner.namespace, "--output", "json"])
    value = json.loads(namespace.stdout.decode("utf-8"))
    labels = value.get("metadata", {}).get("labels", {})
    ensure(
        labels.get("pod-security.kubernetes.io/enforce") == "restricted",
        "namespace does not enforce Kubernetes Restricted Pod Security",
    )


def validate_statefulsets(runner: Runner) -> None:
    statefulsets = item_map(runner.json("get", "statefulset"))
    missing = sorted(REQUIRED_STATEFULSETS - statefulsets.keys())
    ensure(not missing, f"required StatefulSets are missing: {', '.join(missing)}")
    for name in sorted(REQUIRED_STATEFULSETS):
        item = statefulsets[name]
        desired = int(item.get("spec", {}).get("replicas", 1) or 0)
        ready = int(item.get("status", {}).get("readyReplicas", 0) or 0)
        ensure(desired >= 1 and ready == desired, f"StatefulSet {name} is not ready ({ready}/{desired})")


def validate_deployments_and_images(runner: Runner) -> None:
    deployments = item_map(runner.json("get", "deployment"))
    application = {name: item for name, item in deployments.items() if name.startswith("signalchord-")}
    ensure(application, "no SignalChord application Deployments were found")
    for name, item in sorted(application.items()):
        desired = int(item.get("spec", {}).get("replicas", 1) or 0)
        ready = int(item.get("status", {}).get("readyReplicas", 0) or 0)
        ensure(ready == desired and desired >= 1, f"Deployment {name} is not ready ({ready}/{desired})")
        containers = item.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        ensure(containers, f"Deployment {name} has no containers")
        for container in containers:
            image = str(container.get("image", ""))
            ensure("@sha256:" in image, f"Deployment {name} image is not digest pinned: {image}")
            security = container.get("securityContext", {})
            ensure(security.get("allowPrivilegeEscalation") is False, f"Deployment {name} permits privilege escalation")
            ensure(security.get("readOnlyRootFilesystem") is True, f"Deployment {name} root filesystem is writable")


def validate_storage(runner: Runner) -> None:
    claims = runner.json("get", "pvc").get("items", [])
    ensure(claims, "no PersistentVolumeClaims were found")
    pending = [
        str(item.get("metadata", {}).get("name", ""))
        for item in claims
        if item.get("status", {}).get("phase") != "Bound"
    ]
    ensure(not pending, f"PersistentVolumeClaims are not bound: {', '.join(sorted(pending))}")


def validate_services(runner: Runner) -> None:
    services = runner.json("get", "service").get("items", [])
    exposed = []
    for item in services:
        service_type = item.get("spec", {}).get("type", "ClusterIP")
        if service_type not in {"ClusterIP", "ExternalName"}:
            exposed.append(f"{item.get('metadata', {}).get('name')}:{service_type}")
        for port in item.get("spec", {}).get("ports", []):
            if port.get("nodePort"):
                exposed.append(f"{item.get('metadata', {}).get('name')}:nodePort={port['nodePort']}")
    ensure(not exposed, "internal services are externally exposed: " + ", ".join(exposed))


def validate_ingress(runner: Runner, host: str) -> None:
    ingresses = runner.json("get", "ingress").get("items", [])
    ensure(ingresses, "no ingress was found")
    matched = False
    for ingress in ingresses:
        spec = ingress.get("spec", {})
        hosts = [rule.get("host") for rule in spec.get("rules", [])]
        if host in hosts:
            matched = True
            tls_hosts = [value for item in spec.get("tls", []) for value in item.get("hosts", [])]
            ensure(host in tls_hosts, f"ingress for {host} has no TLS host entry")
            ensure(any(item.get("secretName") for item in spec.get("tls", [])), "ingress TLS Secret is missing")
    ensure(matched, f"no ingress rule matches {host}")


def validate_network_policies(runner: Runner) -> None:
    policies = set(item_map(runner.json("get", "networkpolicy")))
    missing = sorted(REQUIRED_NETWORK_POLICIES - policies)
    ensure(not missing, f"required NetworkPolicies are missing: {', '.join(missing)}")


def ssl_context(insecure: bool) -> ssl.SSLContext:
    if insecure:
        return ssl._create_unverified_context()  # noqa: SLF001 - explicit local acceptance option
    return ssl.create_default_context()


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    insecure: bool = False,
    timeout: int = 20,
) -> Any:
    headers = {"Accept": "application/json"}
    payload = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context(insecure)) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AcceptanceError(f"HTTP {exc.code} for {method} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AcceptanceError(f"request failed for {method} {url}: {exc}") from exc
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AcceptanceError(f"non-JSON response from {method} {url}") from exc


def validate_https(host: str, insecure: bool) -> None:
    health = request_json("GET", f"https://{host}/healthz", insecure=insecure)
    ensure(isinstance(health, dict) and health.get("status") == "ok", "HTTPS health response is not healthy")


def fixture_resources(namespace: str, suffix: str, image: str) -> bytes:
    ensure("@sha256:" in image, "--fixture-image must use an immutable sha256 digest")
    name = f"signalchord-acceptance-{suffix}"
    timestamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    article_url = f"http://{name}.{namespace}.svc.cluster.local:8080/article-{suffix}.html"
    feed = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\"><channel>
<title>SignalChord acceptance fixture</title>
<link>{article_url}</link>
<description>Repository-owned synthetic acceptance content.</description>
<item><guid isPermaLink=\"true\">{article_url}</guid><link>{article_url}</link>
<title>Acme Corporation announces Northstar Labs partnership {suffix}</title>
<pubDate>{timestamp}</pubDate></item></channel></rss>
"""
    article = (
        "<html><body><h1>Acme Corporation announces Northstar Labs partnership</h1>"
        f"<p>Synthetic SignalChord acceptance fixture {suffix}. Acme Corporation partnered with Northstar Labs.</p>"
        "</body></html>"
    )
    resources = [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": namespace},
            "data": {"feed.xml": feed, f"article-{suffix}.html": article},
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": {"app": name}},
                    "spec": {
                        "automountServiceAccountToken": False,
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 10001,
                            "runAsGroup": 10001,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [
                            {
                                "name": "fixture",
                                "image": image,
                                "command": ["python", "-m", "http.server", "8080", "--directory", "/fixture"],
                                "ports": [{"name": "http", "containerPort": 8080}],
                                "readinessProbe": {"tcpSocket": {"port": "http"}, "periodSeconds": 2},
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "resources": {
                                    "requests": {"cpu": "10m", "memory": "32Mi"},
                                    "limits": {"cpu": "250m", "memory": "128Mi"},
                                },
                                "volumeMounts": [
                                    {"name": "fixture", "mountPath": "/fixture", "readOnly": True},
                                    {"name": "tmp", "mountPath": "/tmp"},
                                ],
                            }
                        ],
                        "volumes": [
                            {"name": "fixture", "configMap": {"name": name}},
                            {"name": "tmp", "emptyDir": {}},
                        ],
                    },
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"selector": {"app": name}, "ports": [{"name": "http", "port": 8080, "targetPort": "http"}]},
        },
    ]
    return "\n---\n".join(json.dumps(resource, separators=(",", ":")) for resource in resources).encode("utf-8")


def delete_api_resource(base_url: str, collection: str, identifier: str | None, token: str, insecure: bool) -> None:
    if not identifier:
        return
    try:
        request_json("DELETE", f"{base_url}/api/v1/{collection}/{identifier}", token=token, insecure=insecure)
    except AcceptanceError as exc:
        print(f"cleanup warning: {exc}", file=sys.stderr)


def synthetic_canary(runner: Runner, host: str, image: str, insecure: bool, timeout: int) -> None:
    email = os.getenv("SIGNALCHORD_ACCEPTANCE_EMAIL", "")
    password = os.getenv("SIGNALCHORD_ACCEPTANCE_PASSWORD", "")
    organization = os.getenv("SIGNALCHORD_ACCEPTANCE_ORGANIZATION", "")
    ensure(email and password and organization, "canary credentials must be supplied through SIGNALCHORD_ACCEPTANCE_* environment variables")

    suffix = uuid.uuid4().hex[:10]
    fixture_name = f"signalchord-acceptance-{suffix}"
    job_name = f"signalchord-acceptance-{suffix}"
    base_url = f"https://{host}"
    token = ""
    source_id: str | None = None
    watchlist_id: str | None = None
    try:
        runner.run(["kubectl", "apply", "--filename", "-"], input_bytes=fixture_resources(runner.namespace, suffix, image))
        runner.kubectl("rollout", "status", f"deployment/{fixture_name}", "--timeout=180s")

        session = request_json(
            "POST",
            f"{base_url}/api/v1/auth/session",
            body={"email": email, "password": password, "organization_slug": organization},
            insecure=insecure,
        )
        ensure(isinstance(session, dict) and session.get("access_token"), "session endpoint did not return an access token")
        token = str(session["access_token"])

        policies = request_json("GET", f"{base_url}/api/v1/policies", token=token, insecure=insecure)
        ensure(isinstance(policies, list) and any(item.get("active") for item in policies), "no active alert policy exists")
        alerts = request_json("GET", f"{base_url}/api/v1/alerts", token=token, insecure=insecure)
        baseline = {str(item.get("id")) for item in alerts if item.get("id")} if isinstance(alerts, list) else set()

        endpoint = f"http://{fixture_name}.{runner.namespace}.svc.cluster.local:8080/feed.xml"
        source = request_json(
            "POST",
            f"{base_url}/api/v1/sources",
            token=token,
            insecure=insecure,
            body={
                "source": {
                    "name": f"Synthetic acceptance {suffix}",
                    "endpoint": endpoint,
                    "adapter": "rss",
                    "rights_status": "approved",
                    "enabled": True,
                    "requests_per_minute": 10,
                    "raw_retention_days": 1,
                    "policy_metadata": {
                        "owner": "signalchord-release-acceptance",
                        "legal_basis": "first_party_fixture",
                        "permitted_uses": ["synthetic_acceptance"],
                        "attribution": "Repository-owned synthetic fixture",
                        "terms_status": "first_party_fixture",
                        "retention_days": 1,
                        "fixture": True,
                        "license": "repository-owned",
                    },
                }
            },
        )
        ensure(isinstance(source, dict) and source.get("id"), "source creation did not return an ID")
        source_id = str(source["id"])

        watchlist = request_json(
            "POST",
            f"{base_url}/api/v1/watchlists",
            token=token,
            insecure=insecure,
            body={
                "watchlist": {
                    "name": f"Synthetic acceptance {suffix}",
                    "description": "Temporary repository-owned release canary",
                    "items": [{"target_kind": "entity", "target_stable_id": "company:acme", "relevance_weight": 1}],
                }
            },
        )
        ensure(isinstance(watchlist, dict) and watchlist.get("id"), "watchlist creation did not return an ID")
        watchlist_id = str(watchlist["id"])

        runner.kubectl("create", "job", f"--from=cronjob/signalchord-feed-collector", job_name)
        runner.kubectl("wait", "--for=condition=complete", f"job/{job_name}", "--timeout=300s")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = request_json("GET", f"{base_url}/api/v1/alerts", token=token, insecure=insecure)
            if isinstance(current, list):
                new_alerts = [item for item in current if str(item.get("id")) not in baseline]
                if new_alerts:
                    print(f"synthetic canary created {len(new_alerts)} new alert(s)")
                    return
            time.sleep(5)
        raise AcceptanceError(f"synthetic article-to-alert canary produced no new alert within {timeout} seconds")
    finally:
        if token:
            delete_api_resource(base_url, "sources", source_id, token, insecure)
            delete_api_resource(base_url, "watchlists", watchlist_id, token, insecure)
        runner.kubectl("delete", "job", job_name, "--ignore-not-found", check=False)
        runner.kubectl("delete", "service,deployment,configmap", fixture_name, "--ignore-not-found", check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="signalchord")
    parser.add_argument("--host", required=True)
    parser.add_argument("--insecure", action="store_true", help="allow an untrusted TLS certificate for a private drill")
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--fixture-image", help="Python-capable image pinned by sha256; required with --canary")
    parser.add_argument("--canary-timeout", type=int, default=600)
    args = parser.parse_args()

    try:
        runner = Runner(args.namespace)
        validate_namespace(runner)
        validate_statefulsets(runner)
        validate_deployments_and_images(runner)
        validate_storage(runner)
        validate_services(runner)
        validate_ingress(runner, args.host)
        validate_network_policies(runner)
        validate_https(args.host, args.insecure)
        if args.canary:
            ensure(bool(args.fixture_image), "--fixture-image is required with --canary")
            synthetic_canary(runner, args.host, str(args.fixture_image), args.insecure, args.canary_timeout)
        print("SignalChord single-server Kubernetes acceptance passed")
        return 0
    except AcceptanceError as exc:
        print(f"acceptance failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
