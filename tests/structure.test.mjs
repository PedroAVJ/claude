import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import test from "node:test";

const root = fileURLToPath(new URL("..", import.meta.url));
const expected = {
  name: "claude",
  version: "0.5.22",
  url: "https://github.com/PedroAVJ/claude",
};

async function json(...parts) {
  return JSON.parse(await readFile(join(root, ...parts), "utf8"));
}

test("unified dual-client plugin metadata is synchronized", async () => {
  const codex = await json(".codex-plugin", "plugin.json");
  const claude = await json(".claude-plugin", "plugin.json");

  for (const manifest of [codex, claude]) {
    assert.equal(manifest.name, expected.name);
    assert.equal(manifest.version, expected.version);
    assert.equal(manifest.homepage, expected.url);
    assert.equal(manifest.repository, expected.url);
    assert.equal(manifest.skills, "./skills/");
  }

  assert.equal(codex.interface.displayName, "Claude");
  assert.equal(codex.interface.category, "AI");
  assert.equal(codex.mcpServers, "./.mcp.json");
  assert.equal(codex.interface.composerIcon, "./assets/claude-plugin.svg");
  assert.equal(codex.interface.logo, "./assets/claude-plugin.svg");
  assert.equal(claude.dependencies, undefined, "Near is an optional enhancement");
  assert.ok((await readFile(join(root, "assets", "claude-plugin.svg"))).length > 0);

  const pkg = await json("package.json");
  assert.equal(pkg.name, "@pedroavj/claude");
  assert.equal(pkg.version, expected.version);
  assert.equal(pkg.homepage, expected.url + "#readme");
  assert.equal(pkg.repository.url, "git+" + expected.url + ".git");

  const skills = (await readdir(join(root, "skills"), { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  assert.deepEqual(skills, ["claude", "design", "explain", "oracle"]);

  for (const path of [
    "README.md",
    "AGENTS.md",
    "ICON-SOURCES.md",
    ".mcp.json",
    "scripts/launch-claude-design-mcp",
    "scripts/snapshot-claude-design.mjs",
    "scripts/validate-design-snapshot.mjs",
    "vendor/claude-design-mcp/LICENSE",
    "vendor/claude-design-mcp/UPSTREAM.md",
  ]) {
    await access(join(root, path));
  }
});

test("Claude Design MCP is plugin-owned and contains no credentials", async () => {
  const mcp = await json(".mcp.json");
  const server = mcp.mcpServers["claude-design"];

  assert.equal(server.type, "stdio");
  assert.equal(server.command, "/bin/sh");
  assert.deepEqual(server.args, [
    "-c",
    'root=$CLAUDE_PLUGIN_ROOT; if [ -z "$root" ]; then root=.; fi; exec "$root/scripts/launch-claude-design-mcp"',
  ]);
  assert.equal(server.cwd, ".");

  const launcher = await readFile(join(root, "scripts", "launch-claude-design-mcp"), "utf8");
  const bridge = await readFile(
    join(root, "vendor", "claude-design-mcp", "lib", "server.mjs"),
    "utf8",
  );
  const provenance = await readFile(
    join(root, "vendor", "claude-design-mcp", "UPSTREAM.md"),
    "utf8",
  );

  assert.match(launcher, /vendor\/claude-design-mcp\/bin\/claude-design-mcp\.mjs/);
  assert.match(bridge, /refreshAfterUnauthorized/);
  assert.match(bridge, /never opens a browser/);
  assert.doesNotMatch(bridge, /resolveMcpRemoteBin|spawn\(/);
  assert.match(provenance, /5e50b691df5259668cf80fcd41766d4da17a80ce/);

  const committedText = `${JSON.stringify(mcp)}\n${launcher}\n${bridge}\n${provenance}`;
  assert.doesNotMatch(committedText, /sk-ant-[A-Za-z0-9_-]+/);
});

test("Claude Design MCP exposes and accepts read-only tools only", async () => {
  const {
    isAllowedClientMessage,
    isReadOnlyToolName,
    restrictToolsListMessage,
  } = await import("../vendor/claude-design-mcp/lib/server.mjs");

  assert.equal(isReadOnlyToolName("read_file"), true);
  assert.equal(isReadOnlyToolName("list_projects"), true);
  assert.equal(isReadOnlyToolName("write_files"), false);
  assert.equal(isReadOnlyToolName("create_project"), false);
  assert.equal(
    isAllowedClientMessage({
      method: "tools/call",
      params: { name: "read_file" },
    }),
    true,
  );
  assert.equal(
    isAllowedClientMessage({
      method: "tools/call",
      params: { name: "write_files" },
    }),
    false,
  );

  const restricted = restrictToolsListMessage({
    jsonrpc: "2.0",
    id: 1,
    result: {
      tools: [
        { name: "read_file" },
        { name: "write_files" },
        { name: "update_sharing" },
      ],
    },
  });
  assert.deepEqual(restricted.result.tools, [{ name: "read_file" }]);
});

test("ordinary product conversation does not route to Claude Design", async () => {
  const design = await readFile(join(root, "skills", "design", "SKILL.md"), "utf8");
  const conversation = await readFile(join(root, "skills", "claude", "SKILL.md"), "utf8");
  const normalizedDesign = design.replace(/\s+/g, " ");
  const normalizedConversation = conversation.replace(/\s+/g, " ");

  for (const phrase of [
    "Design subject matter is not an invocation of Claude Design",
    "If mutation intent remains ambiguous after explicit entry, default to discussion-only",
    "without asking whether to author",
    "Never create a project, file, prototype, repository mapping, or Git checkpoint merely to obtain an opinion",
    "The presence of design nouns such as “interface,” “screen,” or “reportes” is not an authoring instruction",
  ]) {
    assert.ok(normalizedDesign.includes(phrase));
  }

  assert.ok(normalizedDesign.includes("“Claude, what do you think about voice agents living on a TV?” stays in `claude:claude`"));
  assert.ok(normalizedDesign.includes("“Make the designs for that chat interface” explicitly opens authoring"));
  assert.ok(normalizedConversation.includes("A topic does not become Claude Design merely because it could eventually be designed"));
  assert.ok(normalizedConversation.includes("“Claude, design the room-mode TV interface” uses `claude:design`"));
});
