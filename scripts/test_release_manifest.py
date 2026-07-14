#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from argparse import Namespace
from io import StringIO
from pathlib import Path

import release_manifest


class ReleaseManifestTest(unittest.TestCase):
    def test_builds_manifest_with_digest_pinned_images_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            digests = base / "digests"
            sboms = base / "sboms"
            scans = base / "scans"
            for directory in (digests, sboms, scans):
                directory.mkdir()

            (digests / "digest-web.txt").write_text(
                "ghcr.io/pepitodrop/signalchord-web@sha256:" + "a" * 64 + "\n",
                encoding="utf-8",
            )
            (sboms / "source.spdx.json").write_text("{}", encoding="utf-8")
            (scans / "trivy-image.txt").write_text("no findings", encoding="utf-8")
            source = base / "source.tgz"
            source.write_text("source", encoding="utf-8")

            manifest = release_manifest.build_manifest(
                Namespace(
                    tag="v1.2.3",
                    commit="b" * 40,
                    digests_dir=str(digests),
                    sbom_dir=str(sboms),
                    scan_dir=str(scans),
                    source_archive=str(source),
                )
            )

            release_manifest.validate_manifest(manifest)
            self.assertEqual(manifest["promotion"]["policy"], "promote-by-digest-only")
            self.assertEqual(manifest["images"][0]["ref"].split("@", 1)[0], "ghcr.io/pepitodrop/signalchord-web")

    def test_rejects_mutable_image_references(self) -> None:
        manifest = {
            "schemaVersion": "signalchord.release-manifest.v1",
            "release": {"tag": "v1.2.3", "commit": "b" * 40},
            "images": [{"ref": "ghcr.io/pepitodrop/signalchord-web:v1.2.3"}],
            "sboms": [{"name": "source.spdx.json"}],
            "vulnerabilityReports": [{"name": "trivy.txt"}],
        }

        with self.assertRaisesRegex(ValueError, "digest-pinned"):
            release_manifest.validate_manifest(manifest)

    def test_cli_validate_rejects_missing_artifact_sections(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "signalchord.release-manifest.v1",
                        "release": {"tag": "v1.2.3", "commit": "b" * 40},
                        "images": [{"ref": "ghcr.io/pepitodrop/signalchord-web@sha256:" + "a" * 64}],
                        "sboms": [],
                        "vulnerabilityReports": [{"name": "trivy.txt"}],
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stderr(StringIO()):
                self.assertEqual(release_manifest.main(["validate", "--file", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
