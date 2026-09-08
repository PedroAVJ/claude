# Upstream provenance

- Project: `erdnj/claude-design-mcp`
- Upstream commit: `5e50b691df5259668cf80fcd41766d4da17a80ce`
- License: MIT; see `LICENSE`
- Retrieved and audited: 2026-08-13

`LICENSE`, `bin/claude-design-mcp.mjs`, and `lib/oauth.mjs` match that upstream
commit. `lib/server.mjs` is the locally
audited replacement used by this integration. It removes
the `mcp-remote` child dependency, forwards MCP JSON-RPC directly to Anthropic,
reloads the shared credential store for each request, retries once after a 401,
coordinates rotating refresh tokens, and never launches a generic browser
fallback during server operation.

Anthropic owns the Claude Design service and endpoint. This vendored adapter is
an unofficial compatibility layer and does not imply affiliation with
Anthropic.
