# Git-backed Claude Design history

Use this workflow for every existing Claude Design project or design system
that Fable will mutate. Claude Design chat history and Undo are recovery aids,
not source control.

## Governing repository

The repository that owns the product or design system owns its Claude Design
history. Its root `AGENTS.md` must name the project UUID and role under
`## Claude Design`.

- Consumer projects live with the product they design.
- A design system lives with the product family it governs.
- Multiple related Claude Design projects may share one repository.
- Do not create a workspace-wide registry or place product designs in the
  `claude` plugin repository.
- When ownership is absent or ambiguous, stop before mutation. A binding proves
  design-system usage, not repository ownership.

Use the repository's existing design-artifact location. When it has none,
default to:

```text
docs/design/claude-design/<project-uuid>/
|-- project.json
`-- files/
    `-- <exact Claude Design project-relative paths>
```

Git commits provide the timeline; do not create timestamped copies of the same
project inside one commit.

## Mirror contract

`project.json` uses schema version 1 and records:

```json
{
  "schemaVersion": 1,
  "project": {
    "id": "project UUID",
    "name": "authoritative live name",
    "type": "PROJECT_TYPE_PROJECT or PROJECT_TYPE_DESIGN_SYSTEM",
    "url": "durable claude.ai/design project URL"
  },
  "capturedAt": "RFC 3339 timestamp",
  "source": "Claude Design read-only MCP",
  "files": [
    {
      "path": "exact/project/path.dc.html",
      "size": 123,
      "etag": "opaque live etag",
      "sha256": "lowercase file digest"
    }
  ],
  "excluded": [
    {
      "path": "support.js",
      "size": 123,
      "etag": "opaque live etag",
      "reason": "claude-design-runtime"
    }
  ]
}
```

Mirror every authored source file byte-for-byte beneath `files/`, preserving
its project-relative path. Use `list_files` for the complete tree and
`read_file` for text. Decode only the connector's outer transport escaping;
do not normalize, format, or add a final newline.

Binary assets are source too. Preserve their exact bytes from an already
tracked authoritative source when byte identity is verified, or export them
through an authenticated Claude Design/browser path that does not expose a
temporary token. Record their digest and `etag`. If an authored binary asset
cannot be recovered or matched exactly, the pre-change checkpoint is
incomplete and mutation must wait.

Record these reproducible or supplied files as exclusions rather than copying
them into every mirror:

- `.thumbnail` files;
- Claude Design `support.js` runtime files;
- bound `_ds/` consumer copies;
- generated `_ds_bundle.*`, `_ds_manifest.json`, `_ds_sync.json`, and
  `_adherence.*` outputs; and
- generated preview/vendor files that are not authored design-system source.

Do not exclude authored components, tokens, guidelines, templates, UI kits,
CSS, JavaScript, JSX, prompt files, documentation, fonts, or images merely
because they are nested or inconvenient to extract.

Run the bundled validator from the plugin source when available:

```bash
node scripts/validate-design-snapshot.mjs \
  docs/design/claude-design/<project-uuid>
```

From the plugin source, the authenticated snapshot command performs the live
metadata read, exact text and binary export, manifest refresh, and mirror
replacement for one or more projects without persisting preview tokens:

```bash
node scripts/snapshot-claude-design.mjs \
  --repo /absolute/path/to/governing-repository \
  --project <project-uuid>
```

It verifies manifest identity, exact file sizes and hashes, exclusions, and
unmanifested files. It does not prove that the live project still matches;
re-read live metadata, paths, `etag` values, and contents for each checkpoint.

## Pre-change gate

1. Resolve the authoritative remote and default branch, then work in an
   isolated task clone or branch according to the repository's instructions.
2. Read live project metadata and the complete file tree.
3. Refresh the mirror and `project.json` from the live project.
4. Validate the snapshot and inspect the complete Git diff.
5. Commit the snapshot and repository mapping.
6. Push the task branch and verify the exact commit through `git ls-remote` or
   the provider API.

Only then may Fable mutate the project. A local commit without a verified
remote ref does not pass this gate.

## Post-change gate

1. Verify the intended page visually and exercise the changed interactions.
2. Re-read the live metadata, tree, and changed files after Fable finishes.
3. Refresh the same mirror paths; Git should show the actual design diff.
4. Validate, commit, push, and verify the exact remote commit.
5. Report the design URL and both pre-change and post-change commits.

If Fable changes an unexpected file, preserve it in the mirror and stop for
review rather than hiding it from the Git diff.

## Restore

Before restoring, capture and push the current live state through the same
pre-change gate. Select the desired Git commit, compare its manifest and files
with the current project, then have Fable 5.1 write the exact historical payload
in Claude Design. Re-read the result and require byte equality before recording
the post-restore commit.

Do not treat a historical Git file as permission to overwrite concurrent live
work. Re-read current `etag` values immediately before the restoration turn.
