# Claude

One plugin for working with Claude across conversation, design, explanation,
second opinions, and Claude Code Remote Control.

This project is unofficial and is not affiliated with Anthropic.

## Natural-language routing

- Address Claude directly for an ordinary conversation: “Hey Claude, what do
  you think about this?” The `claude` conversation skill relays the user's exact words from Codex
  to a persistent high-effort Fable 5.1 conversation. That first substantive
  address makes Claude/Fable the participant for the whole one-to-one thread.
- A bare leading or trailing “Claude” or “Fable” still counts as a direct
  address when speech-to-text omits vocative punctuation or produces rough
  grammar. A model name mentioned inside a Codex-directed question does not
  switch the addressee.
- Every unnamed follow-up, reaction, correction, and role request stays with
  Claude/Fable in a Claude-owned thread. A later participant name does not
  transfer ownership; talking directly with another participant requires a
  separate thread.
- Names and roles are independent. Fable can use the same configured role
  contracts as Codex and Spark through `ask_fable.py --role-contract`; the
  runtime preserves the role's reasoning effort and instructions and rejects
  incompatible requirements without downgrading. The user's role registry
  remains the authority; no role catalog is copied into this plugin.
- If Codex mistakenly answers an explicitly Claude-addressed turn and the user corrects it, the
  skill relays the original unanswered user message to the current Claude
  conversation instead of making the user repeat it.
- Cross-thread context and reconstruction stay private to the relay. Normal
  responses contain only Claude's answer; raw transcripts, summaries,
  memory evidence, and added context appear only when the user explicitly asks to
  inspect them. When a rough dictated token conflicts with the established
  subject, the relay uses the smallest internal clarification instead of
  letting the stray token create a new topic.
- The relay runs Fable in the user's normal local Claude Code environment. It
  inherits the default built-in tools—including Bash, filesystem, and web
  access—along with user, project, and local settings; enabled skills, plugins,
  MCP servers, and the current permission mode. For user-specific facts not
  established in the current conversation, Fable can autonomously use the
  configured Near context tools when available. Near is optional; its absence
  never blocks a conversation. The relay keeps retrieval details private
  unless the user asks to inspect them.
- The host has no group chat and never returns separate Codex and Claude voices
  in one thread. If the first request names multiple prospective participants,
  choose one owner or use separate threads. The owner may consult another model
  internally without changing the thread participant.
- Talking with Claude about a product, UX, interaction, workflow, screen, or
  visual idea stays in the ordinary `claude` conversation lane. Asking what
  Claude thinks, requesting critique, or exploring an interface concept does
  not silently invoke Claude Design.
- Route to `design` only when the user explicitly asks Claude to design, create,
  mock up, prototype, edit, change, or refine a concrete design artifact;
  explicitly invokes Claude Design; or asks to inspect or operate a specific
  Claude Design project, design system, component, or link. Within that
  explicit lane, discussion still does not authorize mutation: authoring begins
  only when the user requests the concrete creation or change. The `design` skill
  uses Fable 5.1, while the bundled connector remains read-only for inspection
  and extraction. That explicit authoring request already authorizes sending
  the bounded brief and relevant non-personal design source from the governing
  private repository to Claude Design; it does not authorize credentials,
  personal records, unrelated source, broader sharing, or publication.
- Ask for a visual or HTML explanation to use `explain`.
- Ask Oracle for an evidence-grounded Fable 5.1 second opinion at max effort.
- Address Codex explicitly when the request is for Codex rather than Claude;
  merely mentioning Claude does not reroute the request.

## Model and host boundaries

The conversation skill and Oracle pin `claude-fable-5-1`; the conversation skill requests high effort and persists one Claude session per Codex thread, while Oracle requests max effort. The explainer's visual pass
requests `claude-opus-5`. All delegated model calls disable fallback and verify
`modelUsage` before accepting an answer.

The plugin installs in both Codex and Claude Code. Delegated model workflows
exist to let Codex consult Claude. Inside Claude Code they never spawn a nested
Claude CLI: ordinary requests are answered directly, and Oracle refuses to
misrepresent self-consultation as an outside opinion. Claude Design is
host-neutral in both clients.

If the conversation helper fails, it stops and reports the direct relay
failure. It does not automatically initiate authentication, switch to another
model, or start a fresh CLI conversation. A direct instruction from the user to
log in, reauthenticate, fix an identified sign-in failure, use Chrome or saved
autofill, or keep going after that failure authorizes bounded recovery of the
existing Claude CLI session. Codex may inspect `claude auth status`, run
`claude auth login` once, and use the user's existing authenticated Chrome profile,
Google or Claude session, and saved credential/autofill UI to complete the
ordinary OAuth flow without exposing a secret. The exact live challenge stays
preserved until the CLI confirms success. Account recovery is never initiated;
a CAPTCHA, recovery screen, or one-time-code/passkey step that cannot be
completed by the existing authorized session is reported as the exact blocker.
Chrome-profile, Google-web, Claude-web, and Claude-CLI authentication remain
separate states: none is inferred from another, but an explicitly authorized
recovery may reconcile them through the live browser and must verify the final
CLI state before retrying the original message in its existing conversation.

## Included surfaces

- `skills/claude` continues a high-effort, verbatim Fable 5.1 conversation. Its
  repeated `claude:claude` internal identifier deliberately makes natural
  “Hey Claude…” and “Fable…” addressing select this lane for a new thread;
  unaddressed follow-ups remain with Fable for that whole thread.
- `skills/design` authors through Claude Design and extracts through a read-only
  connector.
- `skills/explain` creates polished standalone HTML explainers.
- `skills/oracle` asks Claude Fable 5.1 for a focused second opinion.
- `scripts/claude_host.py` owns shared host and model-identity checks.
- `scripts/run_design_pass.py` runs the explainer's read-only visual pass.
- `scripts/snapshot-claude-design.mjs` and
  `scripts/validate-design-snapshot.mjs` preserve Git-backed design history.
- `vendor/claude-design-mcp` contains the audited read-only Claude Design
  adapter.

## Claude Design boundary

Claude Design is an authoring and collaboration surface, not a production web
host. Fable 5.1 owns creative design changes in the authenticated website. The
MCP bridge can discover projects, read files and conversations, and extract
artifacts, but it rejects connector-authored mutations.

Repository-to-design-system mappings remain in each governed repository's
existing `AGENTS.md`. Every mutation requires verified pre-change and
post-change Git mirrors. OAuth credentials remain local at
`~/.config/claude-design-mcp/credentials.json` and are never packaged.

Refresh a governed project mirror with:

```bash
npm run snapshot -- --repo /path/to/repository --project PROJECT_UUID
```

## Remote Control service

The plugin preserves the existing `com.pedro.claude-remote-control`
LaunchAgent, Application Support directory, log paths, and configuration names.
Launchd executes Anthropic's signed native `claude` binary directly so macOS
privacy permissions remain attached to Claude Code.

```bash
CLAUDE_REMOTE_CONTROL_WORKSPACE=/path/to/project ./scripts/install-launch-agent.sh
./scripts/status-launch-agent.sh
./scripts/uninstall-launch-agent.sh
```

The service retains its memory-conscious default capacity of four concurrent
sessions. Override it with `CLAUDE_REMOTE_CONTROL_CAPACITY` from 1 through 32.
The existing workspace, permission-mode, Artifact, and Chrome preferences remain
unchanged across the plugin rename.

## Public source

First-party code is MIT licensed. Product names are used for identification;
this project is unofficial and does not imply endorsement. Plugin artwork is
original; see `ICON-SOURCES.md`. Configure credentials in your own client and
OS credential stores, never in tracked source.

Remote Control requires an explicit `CLAUDE_REMOTE_CONTROL_WORKSPACE`. It defaults
to the session label `Mac` and Claude's normal `default` permission mode. Set
`CLAUDE_REMOTE_CONTROL_SESSION_PREFIX` or `CLAUDE_REMOTE_CONTROL_PERMISSION_MODE`
explicitly if your own workflow needs another choice. Keep those preferences
outside Git; upgrading plugin files does not rewrite an existing LaunchAgent.
