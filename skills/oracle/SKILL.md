---
name: oracle
description: Ask Claude Fable 5.1 at max effort through Claude Code for a focused evidence-audited second opinion, with fail-closed model-identity verification and no silent fallback. Use when the user explicitly asks for Oracle or a second opinion; ordinary direct conversation with Claude belongs to claude:claude.
metadata:
  author: the user
  origin: loadout-plugin
  source: hand-written
  provenance: unofficial-not-openai-curated
---

# Oracle

## Overview

Oracle is a max-effort Fable 5.1 second-opinion workflow. It gathers the facts Codex can
verify, sends one focused prompt to **Claude Fable 5.1** through the user's
authenticated Claude Code CLI, verifies the model identity in Claude Code's
result metadata, and then grounds the answer against the local evidence.

Fable 5.1 is the only Oracle model. Do not start a browser session or consult an
additional model as part of Oracle. If the user separately asks for another
model, handle that as a distinct request and do not represent it as Oracle.

The static dossier and zip helpers under this skill directory are legacy tools.
Use them only when the user explicitly asks for an uploadable bundle.

## Host Scope

Oracle is Codex-hosted. It reaches Claude Fable 5.1 from outside the Anthropic
family, which is the entire point of a second opinion.

If you are Claude Code, do not run this skill — you would spawn a nested CLI to
ask the Claude family for an opinion on your own work and present it as an
outside one. `scripts/oracle_fable.py` refuses when `$CLAUDECODE` is set and
exits 2. Answer directly instead, and say plainly that no outside model was
consulted.

## When To Use

Use this skill when the user says things like:

- "ask Oracle"
- "use Oracle"
- "ask Fable 5.1"
- "get Fable's second opinion"
- "use the stronger Claude model"

If the current thread makes the question clear, proceed without asking the
user to restate it.

## Source-Of-Truth Discipline

Before consulting Fable, gather the facts Codex can verify locally.

- Inspect the relevant files, diffs, tests, logs, issue text, and deployment or
  device state first.
- Use the canonical connector or artifact for external state when available.
- Mark verified facts, observations, and inferences distinctly in the prompt.
- Do not ask Fable to fetch data from tools it cannot access.
- Reduce large context to the decision-critical facts. Do not upload a repo or
  personal file unless the user explicitly asked for that transmission.

An explicit Oracle request authorizes sending the relevant nonsensitive prompt
to Anthropic. If the prompt would include credentials, private identifiers,
medical or financial details, private messages, browsing history, or other
sensitive data that the user did not clearly authorize sending to Anthropic,
confirm immediately before transmission.

## Prompt Contract

Build one concise, decision-focused prompt:

```text
I need a blunt second opinion from a senior <domain> expert.

Verified context:
- <verified fact>
- <verified command, log, or device result>
- <current implementation detail>

Constraints:
- <constraint that changes the answer>

Questions:
1. <core decision>
2. <specific failure mode>
3. <practical next experiments>

Separate verified behavior from inference. Prefer a concrete next step over
generic advice.
```

## Claude Fable 5.1 Lane

Use the authenticated native Claude Code CLI. Send the prompt on stdin so it
does not become a shell argument. Run without tools, project discovery, or
session persistence by default:

```bash
python3 <oracle-skill-dir>/scripts/oracle_fable.py
```

Feed the prompt to that process on stdin. The helper sets
`CLAUDE_CODE_NO_MODEL_FALLBACK=1`, invokes this underlying command, and fails
closed if Claude Code attempts model substitution or the identity metadata does
not prove Fable 5.1 answered:

```bash
CLAUDE_CODE_NO_MODEL_FALLBACK=1 claude \
  --safe-mode \
  --model claude-fable-5-1 \
  --effort max \
  --print \
  --system-prompt 'You are Claude Fable 5.1. Give an independent expert answer and separate verified facts from inference.' \
  --tools '' \
  --disable-slash-commands \
  --output-format json \
  --no-session-persistence
```

Pass the prompt through stdin. Parse the JSON result and require all of these:

- `is_error` is false.
- `result` is nonempty.
- `modelUsage` includes `claude-fable-5-1` with output tokens.
- The only permitted non-Fable output is at most 128 tokens from the currently
  observed `claude-haiku-4-5` auxiliary model.
- Any Opus, Sonnet, unknown model, or larger auxiliary contribution fails the
  run instead of being treated as Fable.

Claude Code may use a small auxiliary model internally; that does not replace
the requirement that Fable 5.1 produced the substantive answer. Do not silently
fall back to Sonnet, Opus, Haiku, or another model. A control-model probe may be
used for diagnosis, but it is not an Oracle answer.

Use the canonical identifier, explicit max effort, and the no-fallback
environment tripwire. On
Claude Code 2.1.220, both the `fable` alias and the canonical identifier routed
substantive Oracle prompts to Opus 5 when substitution remained enabled. The
tripwire makes that substitution fail instead. The helper must request
`--effort max`; model-usage validation remains authoritative and fails the run
if the combination no longer resolves substantively to Fable 5.1.

## Failure Rules

- Wait for Fable to complete unless the process reports a concrete failure.
- If the helper fails, report the exact Claude CLI, account, availability, or
  identity-validation failure. Oracle did not produce an answer.
- Never conceal provider unavailability, model-selection mismatch, CLI error,
  or account gating behind output from a fallback model.
- Do not dump the full raw JSON unless the user explicitly asks. Preserve the
  reasoning that changes the decision.

## Response Contract

Codex owns the final response and must ground it against the locally verified
facts. Return:

1. **Verdict** — Codex's direct answer after checking Fable's recommendation
   against the available evidence.
2. **Fable's analysis** — the reasoning and recommendation that materially
   affect the decision.
3. **Evidence check** — which claims Codex verified, challenged, or could not
   verify locally.
4. **Next verification** — the smallest local tests that settle what remains.

If Fable asserts an API, product behavior, or current fact that was not locally
verified, label it as Fable's claim until Codex checks it.
