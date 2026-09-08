#!/usr/bin/env node

import { createHash } from "node:crypto";
import { access, mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ensureAccessToken, MCP_URL } from "../vendor/claude-design-mcp/lib/oauth.mjs";

const PROTOCOL_VERSION = "2025-03-26";
const SOURCE = "Claude Design read-only MCP";

function fail(message) {
  throw new Error(message);
}

function toolText(result) {
  return result?.content?.find((item) => item.type === "text")?.text || "";
}

function parseEventStream(body) {
  const messages = [];
  let data = [];
  const flush = () => {
    if (!data.length) return;
    const joined = data.join("\n");
    data = [];
    if (joined !== "[DONE]") messages.push(JSON.parse(joined));
  };
  for (const line of body.split(/\r?\n/)) {
    if (!line) flush();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  flush();
  return messages;
}

class DesignClient {
  constructor() {
    this.nextId = 1;
    this.sessionId = undefined;
  }

  async post(message, retry = true) {
    const accessToken = await ensureAccessToken();
    const headers = {
      Accept: "application/json, text/event-stream",
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      "MCP-Protocol-Version": PROTOCOL_VERSION,
    };
    if (this.sessionId) headers["Mcp-Session-Id"] = this.sessionId;

    const response = await fetch(MCP_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(message),
    });
    if (response.status === 401 && retry) {
      await ensureAccessToken({ forceRefresh: true });
      return this.post(message, false);
    }

    const nextSessionId = response.headers.get("mcp-session-id");
    if (nextSessionId) this.sessionId = nextSessionId;
    if (response.status === 202 || response.status === 204) return undefined;

    const body = await response.text();
    if (!response.ok) fail(`Claude Design request failed (${response.status})`);
    const contentType = response.headers.get("content-type") || "";
    const messages = contentType.includes("text/event-stream")
      ? parseEventStream(body)
      : [JSON.parse(body)];
    const responseMessage = messages.flat().find((item) => item?.id === message.id);
    if (message.id !== undefined && !responseMessage) fail("Claude Design returned no matching response");
    if (responseMessage?.error) fail(responseMessage.error.message || "Claude Design request failed");
    return responseMessage?.result;
  }

  async initialize() {
    const id = this.nextId++;
    await this.post({
      jsonrpc: "2.0",
      id,
      method: "initialize",
      params: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: "claude-design-snapshot", version: "1" },
      },
    });
    await this.post({ jsonrpc: "2.0", method: "notifications/initialized", params: {} });
  }

  async tool(name, args) {
    const id = this.nextId++;
    return this.post({
      jsonrpc: "2.0",
      id,
      method: "tools/call",
      params: { name, arguments: args },
    });
  }
}

export function decodeTransport(content) {
  return content
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

export function parseWrappedProjectFile(wrapped) {
  const openingEnd = wrapped.indexOf("\n");
  const closing = "\n</untrusted-project-content>";
  const closingStart = wrapped.lastIndexOf(closing);
  if (
    !wrapped.startsWith("<untrusted-project-content ") ||
    openingEnd < 0 ||
    closingStart < 0
  ) {
    fail("Claude Design returned an unexpected file wrapper");
  }
  return Buffer.from(decodeTransport(wrapped.slice(openingEnd + 1, closingStart)), "utf8");
}

export function stripInjectedC2PAProvenance(content) {
  const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (content.subarray(0, 8).equals(pngSignature)) {
    const retained = [content.subarray(0, 8)];
    let offset = 8;
    let stripped = false;
    while (offset + 12 <= content.length) {
      const dataLength = content.readUInt32BE(offset);
      const chunkEnd = offset + 12 + dataLength;
      if (chunkEnd > content.length) return content;
      const type = content.toString("ascii", offset + 4, offset + 8);
      if (type === "caBX") stripped = true;
      else retained.push(content.subarray(offset, chunkEnd));
      offset = chunkEnd;
      if (type === "IEND") break;
    }
    return stripped ? Buffer.concat(retained) : content;
  }

  const text = content.toString("utf8");
  if (!text.startsWith("<svg") || !text.includes("<c2pa:manifest>")) return content;

  const stripped = text
    .replace(/\s+xmlns:c2pa="[^"]*"/, "")
    .replace(/<metadata>\s*<c2pa:manifest>[\s\S]*?<\/c2pa:manifest>\s*<\/metadata>/, "");
  return Buffer.from(stripped, "utf8");
}

export function exclusionReason(path) {
  const segments = path.split("/");
  const name = segments.at(-1);
  if (name === ".thumbnail") return "claude-design-thumbnail";
  if (name === "support.js") return "claude-design-runtime";
  if (segments[0] === "_ds") return "bound-design-system-copy";
  if (/^_ds_(bundle|manifest|sync)\./.test(name) || /^_adherence\./.test(name)) {
    return "generated-design-system-output";
  }
  if (segments[0] === "_preview" || segments[0] === "_vendor") {
    return "generated-preview-runtime";
  }
  return undefined;
}

export function projectFileUrl(serveUrl, projectPath) {
  const url = new URL(serveUrl);
  const marker = "/serve/";
  const markerIndex = url.pathname.indexOf(marker);
  if (markerIndex < 0) fail("Claude Design returned an unexpected preview URL");
  const encodedPath = projectPath.split("/").map(encodeURIComponent).join("/");
  url.pathname = `${url.pathname.slice(0, markerIndex + marker.length)}${encodedPath}`;
  return url;
}

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

async function mapLimit(items, limit, worker) {
  let next = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      await worker(items[index], index);
    }
  });
  await Promise.all(runners);
}

async function readAuthoredFile(client, projectId, entry) {
  const result = await client.tool("read_file", { project_id: projectId, path: entry.path });
  if (!result?.isError) {
    const content = stripInjectedC2PAProvenance(parseWrappedProjectFile(toolText(result)));
    if (content.length !== entry.size) {
      fail(`Text size mismatch for ${entry.path}: expected ${entry.size}, received ${content.length}`);
    }
    return content;
  }
  if (!/binary file/i.test(toolText(result))) {
    fail(`Claude Design could not read ${entry.path}`);
  }
  return undefined;
}

async function previewSource(client, projectId, entries) {
  const anchor = entries.find((entry) => /\.dc\.html$/i.test(entry.path)) ||
    entries.find((entry) => /\.html?$/i.test(entry.path));
  if (!anchor) fail("A binary project needs at least one renderable HTML source file");
  const result = await client.tool("render_preview", { project_id: projectId, path: anchor.path });
  const preview = JSON.parse(toolText(result));
  if (!preview.serve_url) fail("Claude Design returned no authenticated preview URL");
  return preview.serve_url;
}

async function readBinaryFile(serveUrl, entry) {
  const url = projectFileUrl(serveUrl, entry.path);
  const response = await fetch(url, { redirect: "follow" });
  if (!response.ok) fail(`Claude Design could not export binary ${entry.path} (${response.status})`);
  const content = stripInjectedC2PAProvenance(Buffer.from(await response.arrayBuffer()));
  if (content.length !== entry.size) {
    fail(`Binary size mismatch for ${entry.path}: expected ${entry.size}, received ${content.length}`);
  }
  return content;
}

async function writeSnapshot(client, repository, projectId) {
  const [projectResult, listResult] = await Promise.all([
    client.tool("get_project", { project_id: projectId }),
    client.tool("list_files", { project_id: projectId, path: "", depth: -1 }),
  ]);
  const project = JSON.parse(toolText(projectResult));
  const liveFiles = JSON.parse(toolText(listResult));
  if (project.id !== projectId) fail(`Project identity mismatch for ${projectId}`);

  const authored = [];
  const excluded = [];
  for (const entry of liveFiles) {
    const reason = exclusionReason(entry.path);
    if (reason) excluded.push({ ...entry, reason });
    else authored.push(entry);
  }

  const destination = join(repository, "docs", "design", "claude-design", projectId);
  const temporaryRoot = await mkdtemp(join(tmpdir(), `claude-design-${projectId}-`));
  const staged = join(temporaryRoot, projectId);
  const stagedFiles = join(staged, "files");
  await mkdir(stagedFiles, { recursive: true });

  try {
    const mirrored = [];
    const pendingBinary = [];
    await mapLimit(authored, 4, async (entry) => {
      const content = await readAuthoredFile(client, projectId, entry);
      if (content) {
        const destinationFile = join(stagedFiles, ...entry.path.split("/"));
        await mkdir(dirname(destinationFile), { recursive: true });
        await writeFile(destinationFile, content);
        mirrored.push({ ...entry, sha256: sha256(content) });
      } else {
        pendingBinary.push(entry);
      }
    });

    if (pendingBinary.length) {
      const serveUrl = await previewSource(client, projectId, authored);
      await mapLimit(pendingBinary, 4, async (entry) => {
        const content = await readBinaryFile(serveUrl, entry);
        const destinationFile = join(stagedFiles, ...entry.path.split("/"));
        await mkdir(dirname(destinationFile), { recursive: true });
        await writeFile(destinationFile, content);
        mirrored.push({ ...entry, sha256: sha256(content) });
      });
    }

    mirrored.sort((left, right) => left.path.localeCompare(right.path));
    excluded.sort((left, right) => left.path.localeCompare(right.path));
    const manifest = {
      schemaVersion: 1,
      project: {
        id: project.id,
        name: project.name,
        type: project.type,
        url: project.url,
      },
      capturedAt: new Date().toISOString(),
      source: SOURCE,
      files: mirrored.map(({ path, size, etag, sha256: digest }) => ({
        path,
        size,
        etag,
        sha256: digest,
      })),
      excluded: excluded.map(({ path, size, etag, reason }) => ({ path, size, etag, reason })),
    };
    await writeFile(join(staged, "project.json"), `${JSON.stringify(manifest, null, 2)}\n`);

    await mkdir(dirname(destination), { recursive: true });
    await rm(destination, { recursive: true, force: true });
    await rename(staged, destination);
    return { id: projectId, name: project.name, files: mirrored.length, excluded: excluded.length };
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
}

function parseArguments(argv) {
  const args = { projects: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--repo") args.repository = argv[++index];
    else if (value === "--project") args.projects.push(argv[++index]);
    else if (value === "--help" || value === "-h") args.help = true;
    else fail(`Unknown argument: ${value}`);
  }
  return args;
}

function usage() {
  return "Usage: node scripts/snapshot-claude-design.mjs --repo <repository> --project <uuid> [--project <uuid> ...]";
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }
  if (!args.repository || !args.projects.length) fail(usage());
  const repository = resolve(args.repository);
  if (!await access(join(repository, ".git")).then(() => true, () => false)) {
    fail(`Not a Git worktree: ${repository}`);
  }

  const client = new DesignClient();
  await client.initialize();
  for (const projectId of args.projects) {
    const result = await writeSnapshot(client, repository, projectId);
    console.log(JSON.stringify(result));
  }
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
}
