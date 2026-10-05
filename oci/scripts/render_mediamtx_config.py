#!/usr/bin/env python3
"""Render a MediaMTX config without placing secrets in Git."""

from __future__ import annotations

import argparse
import grp
import os
from pathlib import Path
import re
import tempfile


PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"invalid environment line {line_number}")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise ValueError(f"empty key/value on environment line {line_number}")
        if any(char in value for char in "\r\n\"\\"):
            raise ValueError(f"unsafe value for {key}")
        values[key] = value
    return values


def render(template: str, values: dict[str, str]) -> str:
    missing = sorted(set(PLACEHOLDER.findall(template)) - values.keys())
    if missing:
        raise ValueError("missing required values: " + ", ".join(missing))
    result = PLACEHOLDER.sub(lambda match: values[match.group(1)], template)
    if PLACEHOLDER.search(result):
        raise ValueError("unresolved placeholders remain")
    return result


def atomic_write(path: Path, content: str, group: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if group:
            os.chown(temporary, 0, grp.getgrnam(group).gr_gid)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group")
    args = parser.parse_args()
    rendered = render(args.template.read_text(encoding="utf-8"), load_env(args.env_file))
    atomic_write(args.output, rendered, args.group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
