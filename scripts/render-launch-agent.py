#!/usr/bin/env python3
"""Render and validate the Claude Remote Control LaunchAgent template."""

from __future__ import annotations

import argparse
import os
import plistlib
import re
from pathlib import Path
from xml.sax.saxutils import escape


LABEL = "com.pedro.claude-remote-control"


def validate_artifact(value: str) -> str:
    if value not in {"0", "1"}:
        raise SystemExit("Claude Remote Control artifact setting must be 0 or 1")
    return value


def validate_capacity(value: str) -> str:
    try:
        capacity = int(value)
    except ValueError as error:
        raise SystemExit("Claude Remote Control capacity must be an integer") from error
    if not 1 <= capacity <= 32:
        raise SystemExit("Claude Remote Control capacity must be between 1 and 32")
    return str(capacity)


def render(template: Path, output: Path, values: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for name, value in values.items():
        token = f"@{name}@"
        if token not in text:
            raise SystemExit(f"LaunchAgent template is missing {token}")
        text = text.replace(token, escape(value))

    unresolved = sorted(set(re.findall(r"@[A-Z_]+@", text)))
    if unresolved:
        raise SystemExit(f"Unresolved LaunchAgent tokens: {', '.join(unresolved)}")

    data = plistlib.loads(text.encode("utf-8"))
    if data.get("Label") != LABEL:
        raise SystemExit(f"LaunchAgent label must remain {LABEL}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--claude", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--session-prefix", required=True)
    parser.add_argument("--permission-mode", required=True)
    parser.add_argument("--capacity", required=True)
    parser.add_argument("--debug-file", required=True)
    args = parser.parse_args()
    render(
        args.template,
        args.output,
        {
            "CLAUDE": args.claude,
            "WORKSPACE": args.workspace,
            "HOME": args.home,
            "PATH": args.path,
            "ARTIFACT": validate_artifact(args.artifact),
            "SESSION_PREFIX": args.session_prefix,
            "PERMISSION_MODE": args.permission_mode,
            "CAPACITY": validate_capacity(args.capacity),
            "DEBUG_FILE": args.debug_file,
        },
    )


if __name__ == "__main__":
    main()
