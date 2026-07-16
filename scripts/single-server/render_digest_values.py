#!/usr/bin/env python3
"""Convert release image-digests.txt into a fail-closed Helm values file."""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXPECTED = {
    "signalchord-control-plane",
    "signalchord-document-fetcher",
    "signalchord-stream-normalizer",
    "signalchord-python",
    "signalchord-realtime-gateway",
    "signalchord-web",
    "signalchord-feed-collector",
}
LINE = re.compile(r"^(?P<image>[^@\s]+)@(?P<digest>sha256:[0-9a-f]{64})$")


def parse(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = raw.strip()
        if not value:
            continue
        match = LINE.fullmatch(value)
        if not match:
            raise ValueError(f"{path}:{number}: expected image@sha256:<64 lowercase hex>")
        name = match.group("image").rsplit("/", 1)[-1]
        if name not in EXPECTED:
            raise ValueError(f"{path}:{number}: unexpected release image {name}")
        if name in result:
            raise ValueError(f"{path}:{number}: duplicate release image {name}")
        result[name] = match.group("digest")

    missing = sorted(EXPECTED - result.keys())
    if missing:
        raise ValueError("missing release image digests: " + ", ".join(missing))
    return result


def render(values: dict[str, str]) -> str:
    lines = ["global:", "  imageDigests:"]
    lines.extend(f"    {name}: {values[name]}" for name in sorted(values))
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: render_digest_values.py IMAGE_DIGESTS OUTPUT", file=sys.stderr)
        return 2
    source, output = map(Path, argv[1:])
    try:
        content = render(parse(source))
    except (OSError, ValueError) as exc:
        print(f"digest values generation failed: {exc}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"wrote immutable Helm digest values to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
