#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import render_digest_values


DIGESTS = {
    name: "sha256:" + format(index, "064x")
    for index, name in enumerate(sorted(render_digest_values.EXPECTED), start=1)
}


class RenderDigestValuesTest(unittest.TestCase):
    def write(self, root: Path, lines: list[str]) -> Path:
        path = root / "image-digests.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def valid_lines(self) -> list[str]:
        return [f"ghcr.io/pepitodrop/{name}@{digest}" for name, digest in DIGESTS.items()]

    def test_complete_manifest_renders_sorted_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = render_digest_values.parse(self.write(Path(tmp), self.valid_lines()))
            output = render_digest_values.render(result)
            self.assertIn("global:\n  imageDigests:\n", output)
            for name, digest in DIGESTS.items():
                self.assertIn(f"    {name}: {digest}\n", output)

    def test_missing_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "missing release image digests"):
                render_digest_values.parse(self.write(Path(tmp), self.valid_lines()[:-1]))

    def test_tag_or_short_digest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = self.valid_lines()
            lines[0] = lines[0].split("@", 1)[0] + ":v1.0.0"
            with self.assertRaisesRegex(ValueError, "expected image@sha256"):
                render_digest_values.parse(self.write(Path(tmp), lines))

    def test_duplicate_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = self.valid_lines()
            lines.append(lines[0])
            with self.assertRaisesRegex(ValueError, "duplicate release image"):
                render_digest_values.parse(self.write(Path(tmp), lines))

    def test_unexpected_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = self.valid_lines()
            lines.append("ghcr.io/pepitodrop/signalchord-unknown@" + "sha256:" + "f" * 64)
            with self.assertRaisesRegex(ValueError, "unexpected release image"):
                render_digest_values.parse(self.write(Path(tmp), lines))


if __name__ == "__main__":
    unittest.main()
