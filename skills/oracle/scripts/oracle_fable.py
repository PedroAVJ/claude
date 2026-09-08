#!/usr/bin/env python3
"""Run an ephemeral Claude Code consultation pinned to Claude Fable 5.1."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any


# Shared host guard and fallback-disabled environment live at the plugin root,
# so oracle and the frontend passes cannot drift apart on these invariants.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))

from claude_host import (  # noqa: E402
    HostGuardError,
    assert_foreign_host,
    claude_environment,
)


FABLE_CANONICAL_MODEL = "claude-fable-5-1"
FABLE_EFFORT = "max"
ALLOWED_AUXILIARY_MODEL_PREFIX = "claude-haiku-4-5"
MAX_AUXILIARY_OUTPUT_TOKENS = 128


class FableValidationError(RuntimeError):
    """The Claude Code result did not prove that Fable 5.1 answered."""


def _output_tokens(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    value = usage.get("outputTokens", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def validate_fable_result(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise FableValidationError("Claude Code did not return a JSON object.")
    if payload.get("is_error") is not False:
        raise FableValidationError("Claude Code reported an error.")
    result = payload.get("result")
    if not isinstance(result, str) or not result.strip():
        raise FableValidationError("Claude Code returned an empty answer.")

    model_usage = payload.get("modelUsage")
    if not isinstance(model_usage, dict):
        raise FableValidationError("Claude Code returned no modelUsage metadata.")

    fable_output_tokens = 0
    rejected_models: list[tuple[str, int]] = []
    for model_key, usage in model_usage.items():
        canonical = usage.get("canonicalModel") if isinstance(usage, dict) else None
        output_tokens = _output_tokens(usage)
        if isinstance(canonical, str) and canonical.startswith(FABLE_CANONICAL_MODEL):
            fable_output_tokens += output_tokens
        elif (
            isinstance(canonical, str)
            and canonical.startswith(ALLOWED_AUXILIARY_MODEL_PREFIX)
            and output_tokens <= MAX_AUXILIARY_OUTPUT_TOKENS
        ):
            continue
        else:
            label = canonical if isinstance(canonical, str) else str(model_key)
            if output_tokens > 0:
                rejected_models.append((label, output_tokens))

    if fable_output_tokens <= 0:
        observed = ", ".join(name for name, _ in rejected_models) or "none"
        raise FableValidationError(
            f"Fable 5.1 did not produce output; observed models: {observed}."
        )

    if rejected_models:
        observed = ", ".join(
            f"{name} ({tokens} output tokens)"
            for name, tokens in rejected_models
        )
        raise FableValidationError(
            "An unexpected non-Fable model produced output: " + observed
        )


def main() -> int:
    try:
        assert_foreign_host("oracle")
    except HostGuardError as error:
        print(f"oracle_fable: refused: {error}", file=sys.stderr)
        return 2

    prompt = sys.stdin.read()
    if not prompt.strip():
        print("oracle_fable: prompt is empty", file=sys.stderr)
        return 2

    claude = shutil.which("claude")
    if claude is None:
        print("oracle_fable: Claude Code is not installed", file=sys.stderr)
        return 127

    command = [
        claude,
        "--safe-mode",
        "--model",
        FABLE_CANONICAL_MODEL,
        "--effort",
        FABLE_EFFORT,
        "--print",
        "--system-prompt",
        (
            "You are Claude Fable 5.1. Give an independent expert answer and "
            "separate verified facts from inference."
        ),
        "--tools",
        "",
        "--disable-slash-commands",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        env=claude_environment(),
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        print(f"oracle_fable: Claude Code failed: {message}", file=sys.stderr)
        return completed.returncode or 1

    try:
        payload = json.loads(completed.stdout)
        validate_fable_result(payload)
    except (json.JSONDecodeError, FableValidationError) as error:
        print(f"oracle_fable: identity validation failed: {error}", file=sys.stderr)
        return 3

    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
