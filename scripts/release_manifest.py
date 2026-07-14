#!/usr/bin/env python3
"""Build and validate SignalChord release manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_REF_RE = re.compile(r"^[-./a-z0-9]+(?::[0-9]+)?/[-./a-z0-9]+@sha256:[a-f0-9]{64}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")

LOCKFILES = [
    "pnpm-lock.yaml",
    "services/go.sum",
    "services/requirements.txt",
    "apps/control-plane/Gemfile.lock",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_image_refs(digests_dir: Path) -> list[str]:
    refs: list[str] = []
    for path in sorted(digests_dir.glob("digest-*.txt")):
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError(f"{path} is empty")
        refs.append(value)
    if not refs:
        raise ValueError(f"no digest-*.txt files found in {digests_dir}")
    invalid = [ref for ref in refs if IMAGE_REF_RE.fullmatch(ref) is None]
    if invalid:
        raise ValueError("image refs must be registry/name@sha256:<digest>: " + ", ".join(invalid))
    if len(set(refs)) != len(refs):
        raise ValueError("duplicate image digest references found")
    return refs


def artifact_entry(path: Path) -> dict[str, str]:
    return {
        "name": path.name,
        "path": str(path),
        "sha256": sha256_file(path),
    }


def artifact_entries(directory: Path, patterns: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for pattern in patterns:
        entries.extend(artifact_entry(path) for path in sorted(directory.glob(pattern)) if path.is_file())
    return sorted(entries, key=lambda entry: entry["name"])


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if TAG_RE.fullmatch(args.tag) is None:
        raise ValueError("release tag must be vMAJOR.MINOR.PATCH")
    if SHA_RE.fullmatch(args.commit) is None:
        raise ValueError("commit must be a full 40-character lowercase SHA")

    digests_dir = Path(args.digests_dir)
    sbom_dir = Path(args.sbom_dir)
    scan_dir = Path(args.scan_dir)
    source_archive = Path(args.source_archive)
    if not source_archive.is_file():
        raise ValueError(f"source archive not found: {source_archive}")

    image_refs = load_image_refs(digests_dir)
    sboms = artifact_entries(sbom_dir, ["*.spdx.json", "*.cyclonedx.json", "*.json"])
    scans = artifact_entries(scan_dir, ["*.sarif", "*.txt", "*.json"])
    if not sboms:
        raise ValueError("at least one SBOM artifact is required")
    if not scans:
        raise ValueError("at least one vulnerability scan artifact is required")

    return {
        "schemaVersion": "signalchord.release-manifest.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "release": {
            "tag": args.tag,
            "commit": args.commit,
            "sourceArchive": artifact_entry(source_archive),
        },
        "dependencies": {
            "lockfiles": LOCKFILES,
            "frozenInstallRequired": True,
        },
        "images": [{"ref": ref} for ref in image_refs],
        "sboms": sboms,
        "vulnerabilityReports": scans,
        "attestations": {
            "keylessSigning": "sigstore-cosign-github-oidc",
            "verificationRequiredBeforePromotion": True,
        },
        "promotion": {
            "policy": "promote-by-digest-only",
            "productionRebuildAllowed": False,
        },
    }


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != "signalchord.release-manifest.v1":
        raise ValueError("unsupported release manifest schemaVersion")
    release = manifest.get("release", {})
    if TAG_RE.fullmatch(str(release.get("tag", ""))) is None:
        raise ValueError("release.tag is not semantic")
    if SHA_RE.fullmatch(str(release.get("commit", ""))) is None:
        raise ValueError("release.commit is not a full SHA")
    images = manifest.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("manifest must contain at least one image")
    for image in images:
        ref = image.get("ref") if isinstance(image, dict) else None
        if not isinstance(ref, str) or IMAGE_REF_RE.fullmatch(ref) is None:
            raise ValueError(f"image ref is not digest-pinned: {ref}")
    for field in ("sboms", "vulnerabilityReports"):
        entries = manifest.get(field)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"manifest must contain {field}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    build = subcommands.add_parser("build")
    build.add_argument("--tag", required=True)
    build.add_argument("--commit", required=True)
    build.add_argument("--digests-dir", required=True)
    build.add_argument("--sbom-dir", required=True)
    build.add_argument("--scan-dir", required=True)
    build.add_argument("--source-archive", required=True)
    build.add_argument("--output", required=True)

    validate = subcommands.add_parser("validate")
    validate.add_argument("--file", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            manifest = build_manifest(args)
            validate_manifest(manifest)
            Path(args.output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            manifest = json.loads(Path(args.file).read_text(encoding="utf-8"))
            validate_manifest(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"release manifest error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
