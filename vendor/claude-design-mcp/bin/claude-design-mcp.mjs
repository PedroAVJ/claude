#!/usr/bin/env node
/**
 * Unified entrypoint:
 *   npx claude-design-mcp              → MCP stdio server (default)
 *   npx claude-design-mcp server       → MCP stdio server
 *   npx claude-design-mcp login|status|token|env|logout|snippets
 */

import {
  ensureAccessToken,
  login,
  logout,
  status,
  printSnippets,
  STORE_PATH,
  packageInstallSpec,
} from "../lib/oauth.mjs";
import { startServer } from "../lib/server.mjs";

const cmd = process.argv[2];

async function showHelp() {
  const pkg = packageInstallSpec();
  console.log(`claude-design-mcp — Claude Design MCP for any agent

MCP server (default):
  npx -y ${pkg}

Auth:
  npx -y ${pkg} login
  npx -y ${pkg} status
  npx -y ${pkg} token
  npx -y ${pkg} env
  npx -y ${pkg} logout
  npx -y ${pkg} snippets

Credentials: ${STORE_PATH}
`);
}

try {
  if (!cmd || cmd === "server") {
    await startServer();
  } else if (cmd === "login") {
    await login();
  } else if (cmd === "status") {
    await status();
  } else if (cmd === "token") {
    process.stdout.write(await ensureAccessToken());
  } else if (cmd === "env") {
    const token = await ensureAccessToken();
    process.stdout.write(
      `export CLAUDE_DESIGN_OAUTH_TOKEN='${token.replace(/'/g, "'\\''")}'\n`,
    );
  } else if (cmd === "logout") {
    await logout();
  } else if (cmd === "snippets" || cmd === "install") {
    printSnippets();
  } else if (cmd === "help" || cmd === "-h" || cmd === "--help") {
    await showHelp();
  } else {
    console.error(`Unknown command: ${cmd}\n`);
    await showHelp();
    process.exitCode = 1;
  }
} catch (err) {
  console.error(err instanceof Error ? err.message : err);
  if (!cmd || cmd === "server") {
    console.error(`\nRun: npx -y ${packageInstallSpec()} login`);
  }
  process.exitCode = 1;
}
