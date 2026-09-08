#!/usr/bin/env python3
"""Shared host guard and model-identity verification for the Claude plugin.

The model-delegating skills in this plugin spend Claude tokens by shelling out
to the authenticated `claude` CLI. Two invariants apply to those lanes:

1. **Never run inside Claude Code.** This plugin exists so Codex can reach
   Claude. Invoked from Claude Code it would spawn a nested CLI to ask the
   running model for its own opinion — burning a session to launder a self
   answer as a second one. Skill-level host routing keeps these lanes dormant
   inside Claude Code; this runtime guard is the backstop.

2. **Never accept a silent model substitution.** `--model` is a request, not a
   guarantee. The CLI will fall back when the requested model is unavailable,
   and a fallback answer returned as Fable's or Opus's is a lie about what
   produced it. Verify against `modelUsage` and fail closed.
"""

from __future__ import annotations

import os
from typing import Any


# Set by Claude Code in every session it spawns; absent under Codex.
CLAUDE_CODE_ENV_MARKER = "CLAUDECODE"

# Small auxiliary calls (title generation, topic detection) legitimately run on
# a cheap model. Allow them only below a token floor that cannot carry an answer.
AUXILIARY_MODEL_PREFIX = "claude-haiku-4-5"
MAX_AUXILIARY_OUTPUT_TOKENS = 128


class HostGuardError(RuntimeError):
    """This plugin was invoked from the agent it is supposed to delegate to."""


class ModelIdentityError(RuntimeError):
    """The CLI result did not prove the requested model produced the output."""


def running_inside_claude_code() -> bool:
    return bool(os.environ.get(CLAUDE_CODE_ENV_MARKER))


def assert_foreign_host(skill: str) -> None:
    """Refuse to run when the host agent is Claude Code itself."""
    if running_inside_claude_code():
        raise HostGuardError(
            f"{skill} is a Codex-hosted skill and refuses to run inside Claude Code "
            f"(${CLAUDE_CODE_ENV_MARKER} is set). Asking Claude to shell out to "
            f"Claude does not produce a second opinion or an outside implementation "
            f"pass — do the work directly instead."
        )


def claude_environment() -> dict[str, str]:
    """Environment for a delegated CLI call, with model fallback disabled."""
    environment = dict(os.environ)
    environment["CLAUDE_CODE_NO_MODEL_FALLBACK"] = "1"
    return environment


def _output_tokens(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    value = usage.get("outputTokens", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def assert_model_produced_output(
    model_usage: Any,
    canonical_model: str,
    *,
    allow_auxiliary_tool_output: bool = False,
) -> None:
    """Fail unless `canonical_model` produced the substantive output.

    Rejects both an empty contribution from the requested model and any
    non-auxiliary output from a model that was not requested. A caller may
    permit larger Haiku tool-worker output only after independently proving
    that the visible assistant messages came from `canonical_model`.
    """
    if not isinstance(model_usage, dict):
        raise ModelIdentityError("Claude Code returned no modelUsage metadata.")

    requested_output_tokens = 0
    rejected: list[tuple[str, int]] = []

    for model_key, usage in model_usage.items():
        canonical = usage.get("canonicalModel") if isinstance(usage, dict) else None
        output_tokens = _output_tokens(usage)

        if isinstance(canonical, str) and canonical.startswith(canonical_model):
            requested_output_tokens += output_tokens
        elif (
            isinstance(canonical, str)
            and canonical.startswith(AUXILIARY_MODEL_PREFIX)
            and (
                output_tokens <= MAX_AUXILIARY_OUTPUT_TOKENS
                or allow_auxiliary_tool_output
            )
        ):
            continue
        elif output_tokens > 0:
            label = canonical if isinstance(canonical, str) else str(model_key)
            rejected.append((label, output_tokens))

    if rejected:
        detail = ", ".join(f"{name} ({tokens} output tokens)" for name, tokens in rejected)
        raise ModelIdentityError(
            f"Expected only {canonical_model} to produce output, but got: {detail}. "
            f"Refusing to present a fallback model's answer as {canonical_model}'s."
        )

    if requested_output_tokens <= 0:
        raise ModelIdentityError(
            f"{canonical_model} produced no output tokens. The requested model did "
            f"not answer; treat this as unavailable rather than retrying silently."
        )
