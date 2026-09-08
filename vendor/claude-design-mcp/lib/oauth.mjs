/**
 * Shared Claude Design OAuth helpers (same flow as Claude Code /design-login).
 */

import { createHash, randomBytes } from "node:crypto";
import { createInterface } from "node:readline";
import { mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

export const DESIGN_CLIENT_ID = "59637612-477b-4836-a601-b0589eda7704";
export const SCOPES = ["user:design:read", "user:design:write"];
export const AUTHORIZE_URL = "https://claude.com/cai/oauth/authorize";
export const TOKEN_URL = "https://platform.claude.com/v1/oauth/token";
export const MANUAL_REDIRECT_URL =
  "https://platform.claude.com/oauth/code/callback";
export const MCP_URL = "https://api.anthropic.com/v1/design/mcp";

export const STORE_PATH =
  process.env.CLAUDE_DESIGN_MCP_CREDENTIALS ||
  join(homedir(), ".config", "claude-design-mcp", "credentials.json");

const REFRESH_SKEW_MS = 60_000;

const require = createRequire(import.meta.url);
const pkg = require(join(dirname(fileURLToPath(import.meta.url)), "..", "package.json"));

/** npx install spec derived from package.json repository (e.g. github:owner/repo). */
export function packageInstallSpec() {
  const fromEnv = process.env.CLAUDE_DESIGN_MCP_INSTALL_SPEC;
  if (fromEnv) return fromEnv;
  const raw = pkg.repository?.url || pkg.repository || "";
  const url = typeof raw === "string" ? raw : raw.url || "";
  const match = url.match(/github\.com[/:]([^/]+)\/([^/.]+)/i);
  if (match) return `github:${match[1]}/${match[2]}`;
  return pkg.name || "claude-design-mcp";
}

function b64url(buf) {
  return Buffer.from(buf)
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function pkce() {
  const verifier = b64url(randomBytes(32));
  const challenge = b64url(createHash("sha256").update(verifier).digest());
  return { verifier, challenge };
}

function makeState() {
  return b64url(randomBytes(32));
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

export async function loadStore() {
  return readJson(STORE_PATH);
}

export async function saveStore(data) {
  await mkdir(dirname(STORE_PATH), { recursive: true });
  await writeFile(STORE_PATH, JSON.stringify(data, null, 2), { mode: 0o600 });
}

function openBrowser(url) {
  const platform = process.platform;
  if (platform === "darwin") spawn("open", [url], { detached: true, stdio: "ignore" });
  else if (platform === "win32")
    spawn("cmd", ["/c", "start", "", url], { detached: true, stdio: "ignore" });
  else spawn("xdg-open", [url], { detached: true, stdio: "ignore" });
}

function buildAuthorizeUrl({ challenge, state }) {
  const authUrl = new URL(AUTHORIZE_URL);
  authUrl.searchParams.append("code", "true");
  authUrl.searchParams.append("client_id", DESIGN_CLIENT_ID);
  authUrl.searchParams.append("response_type", "code");
  authUrl.searchParams.append("redirect_uri", MANUAL_REDIRECT_URL);
  authUrl.searchParams.append("scope", SCOPES.join(" "));
  authUrl.searchParams.append("code_challenge", challenge);
  authUrl.searchParams.append("code_challenge_method", "S256");
  authUrl.searchParams.append("state", state);
  return authUrl.toString();
}

async function exchangeCode({ code, state, verifier }) {
  const body = {
    grant_type: "authorization_code",
    code,
    redirect_uri: MANUAL_REDIRECT_URL,
    client_id: DESIGN_CLIENT_ID,
    code_verifier: verifier,
    state,
  };
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Token exchange failed (${res.status}): ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

async function refreshTokens(store) {
  const body = {
    grant_type: "refresh_token",
    refresh_token: store.refreshToken,
    client_id: store.clientId || DESIGN_CLIENT_ID,
    scope: (store.scopes?.length ? store.scopes : SCOPES).join(" "),
  };
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Token refresh failed (${res.status}): ${text.slice(0, 500)}`);
  }
  const data = JSON.parse(text);
  const next = {
    ...store,
    accessToken: data.access_token,
    refreshToken: data.refresh_token || store.refreshToken,
    expiresAt: Date.now() + Number(data.expires_in || 3600) * 1000,
    scopes:
      typeof data.scope === "string" ? data.scope.split(" ").filter(Boolean) : store.scopes,
    clientId: store.clientId || DESIGN_CLIENT_ID,
    updatedAt: new Date().toISOString(),
  };
  const missing = SCOPES.filter((s) => !(next.scopes || []).includes(s));
  if (missing.length) {
    throw new Error(`Refresh did not grant design scopes (missing: ${missing.join(", ")})`);
  }
  await saveStore(next);
  return next;
}

function toStore(tokenResponse) {
  const scopes =
    typeof tokenResponse.scope === "string"
      ? tokenResponse.scope.split(" ").filter(Boolean)
      : SCOPES;
  return {
    accessToken: tokenResponse.access_token,
    refreshToken: tokenResponse.refresh_token,
    expiresAt: Date.now() + Number(tokenResponse.expires_in || 3600) * 1000,
    scopes,
    clientId: DESIGN_CLIENT_ID,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export async function ensureAccessToken({ forceRefresh = false } = {}) {
  let store = await loadStore();
  if (!store?.accessToken || !store?.refreshToken) {
    throw new Error(`Not logged in. Run: npx -y ${packageInstallSpec()} login`);
  }
  const expired =
    forceRefresh || !store.expiresAt || Date.now() >= store.expiresAt - REFRESH_SKEW_MS;
  if (expired) store = await refreshTokens(store);
  return store.accessToken;
}

function ask(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolveAsk) => {
    rl.question(question, (answer) => {
      rl.close();
      resolveAsk(answer);
    });
  });
}

function parsePastedCode(raw) {
  const trimmed = raw.trim().replace(/^["']|["']$/g, "");
  const [code, state, ...rest] = trimmed.split("#");
  if (!code || !state || rest.length) return null;
  return { code, state };
}

export async function login() {
  const { verifier, challenge } = pkce();
  const state = makeState();
  const authUrl = buildAuthorizeUrl({ challenge, state });

  console.log("Opening browser for Claude Design authorization…");
  console.log("(Same manual flow as Claude Code /design-login)\n");
  console.log(authUrl);
  console.log("");
  openBrowser(authUrl);

  console.log("After you approve access, the page shows a code.");
  console.log("Paste the FULL value (it looks like: CODE#STATE)\n");

  const pasted = await ask("Paste code here > ");
  const parsed = parsePastedCode(pasted);
  if (!parsed) {
    throw new Error(
      'Invalid code. Paste the full value including "#", e.g. abc123#xyz789',
    );
  }
  if (parsed.state !== state) {
    throw new Error(
      "Invalid state parameter. Paste the code from THIS login attempt (not an older tab).",
    );
  }

  const tokens = await exchangeCode({
    code: parsed.code,
    state: parsed.state,
    verifier,
  });
  const store = toStore(tokens);
  const missing = SCOPES.filter((s) => !store.scopes.includes(s));
  if (missing.length) {
    throw new Error(
      `Authorization server did not grant design scopes (missing: ${missing.join(", ")})`,
    );
  }
  await saveStore(store);
  console.log("\nDesign-system access authorized.");
  console.log(`Saved credentials to ${STORE_PATH}`);
  console.log(`Scopes: ${store.scopes.join(" ")}`);
  console.log(`Expires: ${new Date(store.expiresAt).toISOString()}`);
}

export async function status() {
  const store = await loadStore();
  if (!store) {
    console.log("status: logged_out");
    console.log("store:", STORE_PATH);
    return;
  }
  const expired = !store.expiresAt || Date.now() >= store.expiresAt;
  console.log("status:", expired ? "expired" : "logged_in");
  console.log("store:", STORE_PATH);
  console.log("clientId:", store.clientId);
  console.log("scopes:", (store.scopes || []).join(" "));
  console.log(
    "expiresAt:",
    store.expiresAt ? new Date(store.expiresAt).toISOString() : "unknown",
  );
}

export async function logout() {
  await rm(STORE_PATH, { force: true });
  console.log("Logged out. Removed", STORE_PATH);
}

export function printSnippets() {
  const pkg = packageInstallSpec();
  console.log(`# 1) Login once
npx -y ${pkg} login

# 2a) Cursor / Claude Code (.cursor/mcp.json or .mcp.json)
{
  "mcpServers": {
    "claude-design": {
      "command": "npx",
      "args": ["-y", "${pkg}"]
    }
  }
}

# 2b) Codex (~/.codex/config.toml)
[mcp_servers.claude-design]
command = "npx"
args = ["-y", "${pkg}"]
enabled = true

# 2c) HTTP hosts with bearer env
#   eval "$(npx -y ${pkg} env)"
# bearer_token_env_var = "CLAUDE_DESIGN_OAUTH_TOKEN"
`);
}
