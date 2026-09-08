# Repository guidance

- This repository is the canonical source for the dual-client `claude` plugin.
- Keep one user-facing Claude namespace. Ordinary conversation, Claude Design,
  visual explainers, Oracle, and Remote Control belong here as separate skills
  or stable runtime surfaces rather than separate plugins.
- Keep the Codex and Claude manifests synchronized. Model-delegating workflows
  run only from Codex; inside Claude Code they must answer directly or refuse
  self-consultation without spawning another Claude CLI. Claude Design remains
  host-neutral and available in both clients.
- Marketplace catalogs reference this repository; do not duplicate runtime
  behavior into a marketplace repository.
- Preserve `com.pedro.claude-remote-control`, its stable Application Support
  path, environment-variable names, existing credentials, and the persistent
  Fable relay state path across releases and repository renames.
- Keep credentials and personal data out of Git.
- Keep the `claude` conversation lane separate from Oracle: it is a persistent verbatim conversation
  relay, while Oracle is an evidence-audited second opinion.
- Keep retrieved cross-thread context private to the Claude relay. Never expose
  raw transcripts, summaries, memory evidence, or added context unless the user
  explicitly asks to inspect them. Resolve obvious dictated-word conflicts with
  the smallest internal clarification; do not let a stray transcription token
  create a new topic.
- Near is an optional context enhancement, never a prerequisite for ordinary
  conversation. Launch the relay in the user's normal Claude Code
  environment: preserve user, project, and local settings; the default built-in
  tool set including Bash, filesystem, and web tools; enabled skills, plugins,
  and MCP servers; and the user's current permission mode. Do not reintroduce a
  restrictive tool allowlist, strict MCP configuration, blank setting sources,
  or disabled slash commands. Keep Fable model verification and use the
  configured Near context tools when available while allowing all normal customizations.
- Treat a bare leading or trailing `Claude` or `Fable` in informal dictated text
  as an explicit address without requiring vocative punctuation.
- Creative authoring belongs to Claude Design with Fable 5.1 visibly selected.
  Keep the MCP bridge read-only so calling agents can inspect and extract files
  without bypassing the selected designer.
- Route to Claude Design only when the user explicitly asks Claude to design,
  create, mock up, prototype, edit, change, or refine a concrete design
  artifact; explicitly invokes Claude Design; or asks to inspect or operate a
  specific Claude Design project, system, component, or link. Product, UX,
  interaction, workflow, screen, and visual topics remain ordinary Claude
  conversation when the user is discussing an idea, asking what Claude thinks,
  requesting critique, or reflecting without that explicit design action.
- Once an explicit Claude Design context exists, questions, reactions, and
  clarification remain discussion-only unless the user authorizes a concrete
  artifact creation or change.
- An explicit Claude Design authoring request also authorizes the bounded brief
  and relevant non-personal design-source transmission needed to perform that
  work in the authenticated Claude Design workspace. Do not ask for a redundant
  confirmation merely because the governing repository or project is private;
  exclude credentials, personal records, and unrelated source, and stop only
  when those are genuinely required or the action expands access or sharing.
- Every Claude Design mutation requires the validated Git-backed pre-change and
  post-change checkpoints documented in
  `skills/design/references/version-control.md`.
- Preserve the vendored Claude Design adapter's upstream attribution and pinned
  commit. Keep OAuth credentials outside the plugin at the documented local
  credential path.
- Bump the Codex manifest, Claude manifest, and package version together and run
  `npm test` before publishing.
