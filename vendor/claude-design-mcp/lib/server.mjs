import { createInterface } from "node:readline";
import { ensureAccessToken, MCP_URL } from "./oauth.mjs";

const DEFAULT_PROTOCOL_VERSION = "2025-03-26";
const MAX_ERROR_BODY_LENGTH = 500;

export const READ_ONLY_TOOL_NAMES = new Set([
  "get_claude_design_prompt",
  "get_conversation",
  "get_project",
  "list_comments",
  "list_design_systems",
  "list_files",
  "list_members",
  "list_projects",
  "read_design_skill",
  "read_file",
  "render_preview",
]);

let protocolVersion = DEFAULT_PROTOCOL_VERSION;
let sessionId;
let refreshInFlight;

function redact(text) {
  return String(text).replace(/sk-ant-[A-Za-z0-9_-]+/g, "[REDACTED]");
}

function writeMessage(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function writeError(id, code, message, data) {
  const error = { code, message };
  if (data) error.data = data;
  writeMessage({ jsonrpc: "2.0", id: id ?? null, error });
}

export function isReadOnlyToolName(name) {
  return typeof name === "string" && READ_ONLY_TOOL_NAMES.has(name);
}

export function isAllowedClientMessage(message) {
  return message?.method !== "tools/call" ||
    isReadOnlyToolName(message.params?.name);
}

export function restrictToolsListMessage(message) {
  if (Array.isArray(message)) return message.map(restrictToolsListMessage);
  if (!message || typeof message !== "object") return message;
  if (!Array.isArray(message.result?.tools)) return message;

  return {
    ...message,
    result: {
      ...message.result,
      tools: message.result.tools.filter((tool) =>
        isReadOnlyToolName(tool?.name)
      ),
    },
  };
}

async function refreshAfterUnauthorized(rejectedToken) {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    // Another long-lived bridge may already have refreshed the shared store.
    const currentToken = await ensureAccessToken();
    if (currentToken !== rejectedToken) return currentToken;

    try {
      return await ensureAccessToken({ forceRefresh: true });
    } catch (refreshError) {
      // Anthropic rotates refresh tokens. If another process won that race,
      // reload the store and use the token it wrote instead of failing.
      const recoveredToken = await ensureAccessToken();
      if (recoveredToken !== rejectedToken) return recoveredToken;
      throw refreshError;
    }
  })().finally(() => {
    refreshInFlight = undefined;
  });

  return refreshInFlight;
}

async function postToDesign(message, accessToken) {
  const headers = {
    Accept: "application/json, text/event-stream",
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
    "MCP-Protocol-Version": protocolVersion,
  };
  if (sessionId) headers["Mcp-Session-Id"] = sessionId;

  return fetch(MCP_URL, {
    method: "POST",
    headers,
    body: JSON.stringify(message),
  });
}

function emitEventStream(body) {
  let dataLines = [];

  const flush = () => {
    if (!dataLines.length) return;
    const data = dataLines.join("\n");
    dataLines = [];
    if (data === "[DONE]") return;
    try {
      writeMessage(restrictToolsListMessage(JSON.parse(data)));
    } catch (error) {
      console.error(`Claude Design returned invalid SSE data: ${redact(error.message)}`);
    }
  };

  for (const line of body.split(/\r?\n/)) {
    if (line === "") flush();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  flush();
}

async function emitResponse(response, request) {
  if (response.status === 202 || response.status === 204) return;

  const body = await response.text();
  if (!response.ok) {
    const detail = redact(body).slice(0, MAX_ERROR_BODY_LENGTH);
    if (request.id !== undefined) {
      writeError(request.id, -32000, `Claude Design request failed (${response.status})`, detail);
    } else {
      console.error(`Claude Design request failed (${response.status}): ${detail}`);
    }
    return;
  }

  if (!body.trim()) return;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream")) {
    emitEventStream(body);
    return;
  }

  try {
    const parsed = restrictToolsListMessage(JSON.parse(body));
    if (Array.isArray(parsed)) parsed.forEach(writeMessage);
    else writeMessage(parsed);
  } catch (error) {
    if (request.id !== undefined) {
      writeError(request.id, -32700, "Claude Design returned invalid JSON");
    }
    console.error(`Claude Design returned invalid JSON: ${redact(error.message)}`);
  }
}

async function handleMessage(message) {
  if (Array.isArray(message)) {
    for (const request of message) await handleMessage(request);
    return;
  }

  if (message?.method === "initialize" && message.params?.protocolVersion) {
    protocolVersion = message.params.protocolVersion;
  }

  if (!isAllowedClientMessage(message)) {
    writeError(
      message.id,
      -32601,
      "Claude Design MCP is read-only. Use Claude Design in Chrome with Fable 5.1 selected for project or design mutations.",
    );
    return;
  }

  let accessToken = await ensureAccessToken();
  let response = await postToDesign(message, accessToken);

  if (response.status === 401) {
    accessToken = await refreshAfterUnauthorized(accessToken);
    response = await postToDesign(message, accessToken);
  }

  const nextSessionId = response.headers.get("mcp-session-id");
  if (nextSessionId) sessionId = nextSessionId;
  await emitResponse(response, message);
}

/**
 * Start a direct stdio-to-HTTP bridge for Anthropic's Design MCP.
 *
 * The previous mcp-remote child cached its bearer token for the lifetime of
 * the process. On expiry it launched a generic OAuth fallback in Safari. This
 * bridge reloads the shared credential store for every request, refreshes once
 * after a 401, and never opens a browser.
 */
export async function startServer() {
  // Fail at startup with the wrapper's normal actionable error if no login exists.
  await ensureAccessToken();

  const pending = new Set();
  const input = createInterface({ input: process.stdin, crlfDelay: Infinity });

  input.on("line", (line) => {
    if (!line.trim()) return;

    let message;
    try {
      message = JSON.parse(line);
    } catch {
      writeError(null, -32700, "Parse error");
      return;
    }

    const operation = handleMessage(message)
      .catch((error) => {
        const detail = redact(error instanceof Error ? error.message : error);
        if (message.id !== undefined) {
          writeError(message.id, -32001, "Claude Design authentication failed", detail);
        }
        console.error(`Claude Design bridge error: ${detail}`);
      })
      .finally(() => pending.delete(operation));
    pending.add(operation);
  });

  await new Promise((resolve) => input.once("close", resolve));
  await Promise.allSettled([...pending]);
}
