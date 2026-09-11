---
name: claude
description: "Required for an ordinary one-to-one thread whose participant is Claude or Fable, including discussion of products, UX, interactions, interfaces, workflows, and visual ideas when the user is not explicitly asking Claude to design or change an artifact and is not operating a named Claude Design resource. Claude/Fable owns every follow-up in that thread, including unnamed messages. Names and configured roles are independent. From Codex, relay the intended message verbatim to Claude Fable 5.1 and return its response without inventing a group chat."
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
  and requests explicitly assigning the first substantive turn to Fable establish
  Claude/Fable as the participant for this thread. Every later message remains
  in this skill, including an unaddressed follow-up, correction, reaction, or
  role assignment.
- A bare `Claude` or `Fable` at the beginning or end of an ordinary request is
  an explicit address even when dictated text omits the comma, punctuation,
  capitalization, or clean grammar. For example, `Claude what is that called a
  motto` is Claude-addressed. Never require vocative punctuation before
  routing it. A model name used as the object of a Codex-directed question,
  such as `Codex, why didn't you use Claude?`, remains Codex-addressed.
- A mention or apparent address to Codex after Claude owns the thread does not
  transfer the thread or add Codex as a second speaker. Treat it as a reference
  or a request for Claude to consult Codex. To talk directly with Codex, the user
  starts a separate Codex thread. Likewise, a Codex-owned thread does not become
  Claude-owned because Claude is mentioned after its first substantive turn.
- An exclusively Claude-addressed request receives Claude's response only;
  never substitute Codex's opinion for it.
- The current host has no group chat. Never return separate Codex and Claude
  voices in one thread or label an ordinary one-to-one reply as though several
  participants were present. If the first request names multiple prospective
  participants, ask which one should own the thread or use separate threads.
  The owner may consult another model internally and remains the sole speaker.

### Keep one participant for the whole thread

Codex names the current main assistant, not a fixed model version. Claude and
Fable are interchangeable names for the same `claude-fable-5-1` participant.
Spark names `gpt-5.3-codex-spark` and belongs to the Codex named-participant
route; never impersonate Spark with Fable.

A new one-to-one thread resolves its participant from the first substantive user
request. If that request addresses Claude or Fable, Claude/Fable owns the whole
thread and the stored Fable session carries every later turn. The user never has
to repeat the participant's name. If the first substantive request names no
participant, Codex owns that separate thread.

Resolve an actual addressee from conversational intent, not every occurrence of
a model name. A quoted name or “Codex, why didn't you use Claude?” does not
select Claude. A bare leading or trailing Claude/Fable still counts as an
address when resolving a new thread. Later participant names never alter the
owner of an established one-to-one thread.

Examples:

- `Thoughts, Fable?` -> Fable.
- After Fable answers, `What does that mean for my jobs?` -> Fable.
- `Fable, continue that explanation.` -> resume the same Fable conversation.
- `Spark, check this file.` in a Fable thread -> Fable may consult Spark but remains the speaker.
- `Claude and Codex, each review this.` as the first request -> choose one owner or use separate threads.
- `Fable, as the Intern, summarize this.` -> Fable with the configured Intern role.
- `Intern, summarize this.` later in the Fable thread -> Fable with the configured Intern role.

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
When the role or effort is not material to the user's request, keep that
execution metadata internal so it does not become a participant label.

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

### Repair a mistaken thread-participant switch

If Codex answers any turn in a Claude-owned thread, do not treat the user's
correction as a new substantive question and do not make him repeat himself.
Locate the most recent user message that was wrongly answered by Codex, relay
that original message verbatim to the current Claude conversation, and return
Claude's answer. Relay the correction itself only if it also contains a new
question the user explicitly wants Claude to answer. Claude remains the thread
participant afterward.

## Host scope

From Codex, relay through the bundled helper below. Inside Claude Code, do not
spawn another Claude CLI: Claude is already the active addressee, so answer
the user directly. The helper requires a Codex thread marker and refuses generic
nested execution.

## Relay contract

- Send the user message intended for Claude verbatim. Normally that is the user's
  latest message in a Claude-owned thread. During mistaken-speaker repair, it is the original unanswered
  user message identified above. Do not answer it yourself, polish it,
  translate it, extract numbered questions, or replace its framing.
- Never substitute Codex for a request in a Claude-owned thread. The
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
  remains only the unlabeled verbatim Fable result.
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
words and Markdown. In a one-to-one Claude-owned thread, return the answer
without a `Claude`, `Fable`, or model label; the thread already identifies its
participant, and the current host has no group chat to disambiguate. For a role
request, report the role and actual effort only when that execution metadata is
material to the user's request. Do not append a Codex verdict, summary, evidence
check, alternative answer, second participant voice, relay context,
reconstructed transcript, memory citations, or tool narration unless the user
explicitly asks to inspect them.
