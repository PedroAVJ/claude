---
name: claude
description: "Required for ordinary conversation addressed to Claude or Fable, including discussion of products, UX, interactions, interfaces, workflows, and visual ideas when the user is not explicitly asking Claude to design or change an artifact and is not operating a named Claude Design resource. A request with no participant name always addresses Codex, regardless of who answered previously. Names and configured roles are independent. From Codex, relay the intended message verbatim to Claude Fable 5.1 and return Claude's clearly labeled response."
metadata:
  author: PedroAVJ
  origin: loadout-plugin
  source: hand-written
  provenance: unofficial-not-openai-curated
---

# Talk to Claude

This is the ordinary conversational lane under the `claude` plugin. It keeps
the user talking to Fable without turning the exchange into a Codex answer,
evidence dossier, consultant persona, or disconnected one-shot prompt.

## Route specialized requests without stealing ordinary conversation

The word “Claude” selects the Claude plugin. Ordinary conversation is the
default, including product and interface topics. Choose another plugin surface
only when the user explicitly requests that surface or its concrete action:

- Use `claude:design` when the user explicitly asks Claude to design, create, make,
  mock up, prototype, edit, change, or refine a concrete design artifact;
  explicitly invokes Claude Design; or asks to inspect or operate a specific
  Claude Design project, design system, component, or link.
- Ordinary discussion, reflection, advice, critique, and chat use this
  `claude:claude` lane even when the subject is a product, UX, interaction,
  interface, workflow, screen, visual direction, or design idea. A topic does
  not become Claude Design merely because it could eventually be designed.
- A standalone HTML or visual explainer uses `claude:explain`.
- An explicit Oracle or evidence-audited second opinion uses `claude:oracle`.

Examples:

- “Claude, what do you think about voice agents living on a TV?” stays in
  `claude:claude`.
- “Claude, critique this product idea” stays in `claude:claude`.
- “Claude, design the room-mode TV interface” uses `claude:design`.
- “Claude, inspect this Claude Design project and tell me what exists” uses
  `claude:design` without authorizing a mutation.

After choosing the correct surface, resolve the addressee and answer ownership:

- “Hey Claude…”, “Claude, what do you think…”, “ask Claude…”, “tell Fable…”,
  and requests explicitly assigning work to Fable use this skill. An unaddressed
  follow-up goes to Codex even after a Fable answer.
- A bare `Claude` or `Fable` at the beginning or end of an ordinary request is
  an explicit address even when dictated text omits the comma, punctuation,
  capitalization, or clean grammar. For example, `Claude what is that called a
  motto` is Claude-addressed. Never require vocative punctuation before
  routing it. A model name used as the object of a Codex-directed question,
  such as `Codex, why didn't you use Claude?`, remains Codex-addressed.
- Messages addressed to Codex remain with Codex even if they discuss Claude, a
  Claude plugin, or a previous Claude answer. Do not route solely because the
  word “Claude” appears.
- An exclusively Claude-addressed request receives Claude's response only;
  never substitute Codex's opinion for it.
- A mixed Codex-and-Claude request receives both answers. Give Codex's
  substantive answer immediately, before any setup, authentication, tool work,
  or Claude relay. Then obtain and label Claude's answer separately. A relay
  failure must never suppress, replace, or delay Codex's answer. Retain the
  Codex answer when presenting the final result.

### Resolve each request independently

Codex names the current main assistant, not a fixed model version. Claude and
Fable are interchangeable names for the same `claude-fable-5-1` participant.
Spark names `gpt-5.3-codex-spark` and belongs to the Codex named-participant
route; never impersonate Spark with Fable.

A request that names no participant is addressed to Codex, regardless of who
answered the previous request. This replaces persistent speaker ownership.
Continuing the stored Fable session when Fable is addressed again preserves
context, not ownership of intervening requests.

Resolve an actual addressee from conversational intent, not every occurrence of
a model name. A quoted name or “Codex, why didn't you use Claude?” does not
select Claude. A bare leading or trailing Claude/Fable still counts as an
address. Multiple named participants receive their assigned contributions.

Examples:

- `Thoughts, Fable?` -> Fable.
- After Fable answers, `What does that mean for my jobs?` -> Codex.
- `Fable, continue that explanation.` -> resume the same Fable conversation.
- `Spark, check this file.` -> Spark through its actual runtime.
- `Claude and Codex, each review this.` -> both, with separate attribution.
- `Fable, as the Intern, summarize this.` -> Fable with the configured Intern role.
- `Intern, summarize this.` -> Codex with the configured Intern role.

### Shared configured roles

A name selects the participant; a role assigns its responsibility. Resolve roles
through `codex:sub-agents` and its read-only `read-roles.py` helper from the live
registry. Do not bundle another role catalog, invent an unconfigured role, or
substitute a Codex agent for a Fable role. Preserve the complete instructions,
reasoning effort, and delegation constraints. The user's explicit participant
selection overrides a role's model selection; other incompatible requirements
make that participant decline the role, never lower the required effort.

For Fable, save the selected-role helper output to an ignored, private task file
and invoke the existing relay with that contract:

```bash
python3 <claude-skill-dir>/scripts/ask_fable.py --role-contract <private-role.json>
```

Supply the user's message on stdin as usual. The relay pins Fable, applies the
role's exact supported effort and instructions, and keeps its conversation
separate from unassigned Fable and other role contracts. Ordinary Fable remains
high effort. Report the returned role and actual effort in the attribution.

If the selected role permits delegation, resolve only its permitted configured
individual delegates with the same registry helper and add
`--delegate-role-contract <private-delegate.json>` for each. These become native
Claude agents with the configured responsibility, Fable model, and reasoning
effort. Honor narrower allowed-delegation instructions; the adapter does not
infer permissions from a prose role description. Individual roles disable native
Agent/Task tools and also receive an instruction against shell or cross-thread
delegation. Do not claim every possible delegation mechanism is tool-disabled.
Unsupported role execution constraints fail before launching; do not silently
ignore or rewrite them. Keep role files and their contents out of public Git,
logs, and replies. Do not change the user's registry to perform a dispatch.

### Repair a mistaken speaker switch

If the user says that a prior turn was meant for Claude after Codex answered it,
do not treat the correction as a new substantive question and do not make him
repeat himself. Locate the most recent user message that was wrongly answered
by Codex, relay that original message verbatim to the current Claude
conversation, and return Claude's answer. Relay the correction itself only if
it also contains a new question the user explicitly wants Claude to answer.

## Host scope

From Codex, relay through the bundled helper below. Inside Claude Code, do not
spawn another Claude CLI: Claude is already the active addressee, so answer
the user directly. The helper requires a Codex thread marker and refuses generic
nested execution.

## Relay contract

- Send the user message intended for Claude verbatim. Normally that is the user's
  latest message. During mistaken-speaker repair, it is the original unanswered
  user message identified above. Do not answer it yourself, polish it,
  translate it, extract numbered questions, or replace its framing.
- Never substitute Codex for an exclusively Claude-addressed request. The
  Claude response must come from Fable 5.1.
- Treat corrections, objections, and reactions as follow-ups. Continue the
  current Fable session for this Codex thread by default.
- Retrieved threads, transcripts, summaries, memory evidence, and added relay
  context are private scaffolding. Never quote, summarize, enumerate, cite, or
  expose them in commentary or the final response unless the user explicitly asks
  to inspect that material. Do not narrate context retrieval or reconstruction;
  when a progress update is needed, say only that the prior conversation was
  found and the relay is continuing.
- Add context only when Fable cannot resolve a referent from the persisted
  conversation. Put the smallest factual addition after the verbatim message
  under `[Context from Codex]`. Fable may use it, but the user's normal response
  remains only the labeled verbatim Fable result.
- Rough dictation can contain a stray word that conflicts with the established
  subject. Keep the user's message verbatim, but when the exact prior conversation
  makes the intended referent clear, add one terse internal clarification and
  tell Fable not to turn the stray token into a new topic. For example, in an
  established voice-mode discussion, `voicemail` may be a transcription error
  for `voice mode`. If the prior evidence does not resolve the ambiguity, do not
  guess; have Fable ask one concise clarification instead.
- If a previous Fable turn was not persisted, start a new session with only the
  smallest relevant reconstruction needed to continue: a concise factual
  summary or a few exact excerpts. Mark it as reconstructed inside the private
  context. Never paste an entire prior transcript merely to restore continuity,
  and never expose the reconstruction to the user unless they ask to inspect it.
- Use `--new` only when the user asks to reset or when reconstructing an
  unpersisted conversation. Never lose a resumable session silently.

An explicit request to ask Claude authorizes sending that nonsensitive message
to Anthropic. Confirm immediately before transmission if Codex would add
sensitive data the user did not clearly authorize sending.

## Fable-only high-effort lane

Run the bundled helper and pass the prompt on stdin:

```bash
python3 <claude-skill-dir>/scripts/ask_fable.py
```

The helper:

- pins `claude-fable-5-1` with high effort and disables model fallback;
- runs in the user's normal local Claude Code environment, preserving user,
  project, and local settings; the default built-in tools including Bash,
  filesystem, and web access; enabled skills, plugins, MCP servers; and the
  user's current permission mode;
- appends the relay-specific conversation guidance to Claude Code's default
  system prompt instead of replacing the normal coding-agent instructions;
- has Fable use `WebSearch` and `WebFetch` when the user asks what the internet
  says, requests a source or verification, asks about a potentially current
  fact, or challenges a factual claim Fable cannot confidently establish;
- may use an independently configured `near@package-manager` installation and
  its `search_context` and `read_context` tools for relevant personal context;
  Near is optional and its absence never blocks an ordinary conversation;
- asks for missing context when the user has not configured a context source;
- can use the normal Claude Code shell, files, web, skills, plugins, MCPs, and
  other configured capabilities when the user's request calls for them;
- persists one Claude session per `CODEX_THREAD_ID`;
- retains the established internal state path across the plugin and skill
  rename so current conversations continue;
- stores only the Claude session identifier, never prompts or responses; and
- rejects the result unless `modelUsage` proves Fable 5.1 produced the
  substantive output.

Use `python3 .../ask_fable.py --new` only for the reset and recovery cases
above. If resume, account, model, effort, or identity validation fails, report
the failure. Do not retry as a fresh CLI conversation or substitute another
model.

## Authentication recovery requires explicit authorization

A helper failure is a transport failure, not automatic authorization to change
an account or its credentials. Report the failure unless the user directly asks
to restore authentication.

- A direct instruction from the user to “log in,” “reauthenticate,” “fix the
  login,” use Chrome or saved autofill, or keep going after an identified
  authentication failure authorizes a bounded recovery of the existing Claude
  CLI session. Do not ask him for redundant confirmation.
- Inspect `claude auth status` first. If recovery is needed and authorized, run
  `claude auth login` once and use the existing user-selected external Chrome profile; do not use the in-app browser. Use the existing Google or
  Claude web session when available. It is permitted to click `Continue with
  Google`, select the user's existing account, and submit Claude's ordinary OAuth
  consent screen for this CLI connection.
- Saved credential or autofill UI may fill a secure field without revealing its
  value. Never request, read, copy, transcribe, or expose a password, passkey
  response, or recovery code, and never persist a secret in chat, shell
  arguments, files, logs, or the clipboard. If the browser produces an OAuth
  handoff code specifically for the waiting `claude auth login` process,
  transfer it only to that exact CLI prompt without displaying or storing it.
- Preserve the exact live authentication tab with `markHandoff()` before a turn
  can end. While a code or approval is pending, never close, reload, navigate
  away from, replace, or restart that sign-in flow.
- Never initiate account recovery, change credentials, choose a recovery path,
  or request or resend a verification email or SMS. If the live flow reaches a
  CAPTCHA, an account-recovery screen, or a one-time-code/passkey step that the
  existing authorized session and saved autofill cannot complete, preserve it
  and report that exact blocker.
- A Chrome profile login, a Google web session, a Claude website session, and
  Claude CLI OAuth are independent states. Never infer one from another.
  Explicit authorization permits reconciling them through the live browser,
  but `claude auth status` must prove the CLI is authenticated afterward.
- Authentication recovery is not a conversation fallback. Do not switch to a
  browser chat, another Claude surface, another model, a fresh CLI
  conversation, or a replacement Codex task. After authentication succeeds,
  retry the original Claude message in the existing helper session.

## Return the answer

Parse the helper's JSON and return its `result` field verbatim, preserving its
words and Markdown. For ordinary conversation, label it `Claude Fable 5.1 (high, verbatim)` so the
speaker is unambiguous in the Codex thread. For a role request, include the
returned role and actual effort, for example `Fable — Intern (low, verbatim)`. Do not append a Codex verdict,
summary, evidence check, or alternative answer to a Claude-only request unless
the user separately asks for Codex's view. For a mixed request, preserve the
already-given Codex answer and then present the separately labeled Claude
response. Do not append relay context, reconstructed transcript, memory
citations, or tool narration unless the user explicitly asks to inspect them.
