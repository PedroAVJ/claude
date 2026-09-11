import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const root = new URL("..", import.meta.url).pathname;

async function text(...parts) {
  return readFile(join(root, ...parts), "utf8");
}

test("Claude Design skill distinguishes projects, systems, pages, and deployments", async () => {
  const skill = await text("skills", "design", "SKILL.md");
  const model = await text("skills", "design", "references", "project-model.md");
  const history = await text("skills", "design", "references", "version-control.md");

  assert.match(skill, /https:\/\/claude\.ai\/design/);
  assert.match(skill, /get_project/);
  assert.match(skill, /Fable 5.1/);
  assert.match(skill, /read-only allowlist/);
  assert.match(skill, /Do not use connector mutations/);
  assert.doesNotMatch(skill, /use `create_project`/);
  assert.doesNotMatch(skill, /call `finalize_plan`/);
  assert.match(skill, /claudeusercontent\.com/);
  assert.match(model, /PROJECT_TYPE_PROJECT/);
  assert.match(model, /PROJECT_TYPE_DESIGN_SYSTEM/);
  assert.match(model, /Bound shell/);
  assert.match(model, /Deployed site/);
  assert.match(skill, /pre-change Git checkpoint/);
  assert.match(skill, /pre-change commit to the authoritative remote/);
  assert.match(history, /Post-change gate/);
  assert.match(history, /Binary assets are source too/);
});

test("snapshot validator proves exact mirrored bytes and rejects drift", async (t) => {
  const scratch = await mkdtemp(join(tmpdir(), "claude-design-snapshot-"));
  t.after(() => rm(scratch, { recursive: true, force: true }));

  const projectId = "c693f481-5f72-47bb-85ea-72bd12827b20";
  const snapshot = join(scratch, projectId);
  const files = join(snapshot, "files");
  const content = Buffer.from("exact design bytes\n", "utf8");
  await mkdir(files, { recursive: true });
  await writeFile(join(files, "Page.dc.html"), content);
  await writeFile(
    join(snapshot, "project.json"),
    JSON.stringify({
      schemaVersion: 1,
      project: {
        id: projectId,
        name: "Test",
        type: "PROJECT_TYPE_PROJECT",
        url: `https://claude.ai/design/p/${projectId}`,
      },
      capturedAt: "2026-08-27T00:00:00Z",
      source: "Claude Design read-only MCP",
      files: [{
        path: "Page.dc.html",
        size: content.length,
        etag: "1",
        sha256: createHash("sha256").update(content).digest("hex"),
      }],
      excluded: [],
    }, null, 2),
  );

  const validator = join(root, "scripts", "validate-design-snapshot.mjs");
  const valid = spawnSync(process.execPath, [validator, snapshot], { encoding: "utf8" });
  assert.equal(valid.status, 0, valid.stderr);

  await writeFile(join(files, "Page.dc.html"), "changed\n");
  const drifted = spawnSync(process.execPath, [validator, snapshot], { encoding: "utf8" });
  assert.equal(drifted.status, 1);
  assert.match(drifted.stderr, /mismatch/);
});

test("snapshot exporter preserves transport bytes and excludes reproducible runtime files", async () => {
  const {
    decodeTransport,
    exclusionReason,
    parseWrappedProjectFile,
    projectFileUrl,
    stripInjectedC2PAProvenance,
  } = await import("../scripts/snapshot-claude-design.mjs");

  assert.equal(decodeTransport("&amp;lt; &lt;x&gt;"), "&lt; <x>");
  assert.deepEqual(
    parseWrappedProjectFile('<untrusted-project-content path="x" etag="1">\nline &amp; value\n\n</untrusted-project-content>\n(The body above is escaped.)'),
    Buffer.from("line & value\n"),
  );
  assert.equal(exclusionReason("templates/ios/.thumbnail"), "claude-design-thumbnail");
  assert.equal(exclusionReason("_vendor/react.js"), "generated-preview-runtime");
  assert.equal(exclusionReason("components/Button.jsx"), undefined);

  const authoredSvg = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>';
  const transportedSvg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:c2pa="http://c2pa.org/manifest"><metadata><c2pa:manifest>transport-only</c2pa:manifest></metadata><rect width="1" height="1"/></svg>';
  assert.equal(stripInjectedC2PAProvenance(Buffer.from(transportedSvg)).toString(), authoredSvg);
  assert.equal(stripInjectedC2PAProvenance(Buffer.from(authoredSvg)).toString(), authoredSvg);

  const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const pngChunk = (type, data = Buffer.alloc(0)) => {
    const chunk = Buffer.alloc(12 + data.length);
    chunk.writeUInt32BE(data.length, 0);
    chunk.write(type, 4, 4, "ascii");
    data.copy(chunk, 8);
    return chunk;
  };
  const imageData = pngChunk("IDAT", Buffer.from("pixels"));
  const end = pngChunk("IEND");
  const cleanPng = Buffer.concat([pngSignature, imageData, end]);
  const transportedPng = Buffer.concat([pngSignature, pngChunk("caBX", Buffer.from("transport-only")), imageData, end]);
  assert.deepEqual(stripInjectedC2PAProvenance(transportedPng), cleanPng);
  assert.deepEqual(stripInjectedC2PAProvenance(cleanPng), cleanPng);

  const resolved = projectFileUrl(
    "https://example.claudeusercontent.com/v1/design/projects/id/serve/Page.dc.html?t=secret&direct=1",
    "assets/a b.png",
  );
  assert.equal(resolved.pathname, "/v1/design/projects/id/serve/assets/a%20b.png");
  assert.equal(resolved.searchParams.get("t"), "secret");
});

test("Claude manifest exposes the same released skill directory", async () => {
  const codex = JSON.parse(await text(".codex-plugin", "plugin.json"));
  const claude = JSON.parse(await text(".claude-plugin", "plugin.json"));

  assert.equal(claude.name, codex.name);
  assert.equal(claude.version, codex.version);
  assert.equal(claude.skills, "./skills/");
});

test("skill interface describes the Fable authoring boundary", async () => {
  const interfaceYaml = await text(
    "skills",
    "design",
    "agents",
    "openai.yaml",
  );
  assert.match(interfaceYaml, /Fable 5.1/);
  assert.match(interfaceYaml, /concrete design artifact/);
  assert.match(interfaceYaml, /ordinary product conversation in \$claude/);
});

test("natural-language routing requires an explicit Claude Design entry", async () => {
  const design = await text("skills", "design", "SKILL.md");
  const ask = await text("skills", "claude", "SKILL.md");

  assert.match(design, /Design subject matter is not an invocation of Claude Design/);
  assert.match(design, /explicitly asks Claude to design, create, make, mock up, prototype/);
  assert.match(design, /voice agents living on a TV/);
  assert.match(design, /host's standing browser instructions/);
  assert.match(design, /default to\s+discussion-only/);
  assert.match(design, /does \*\*not\*\* by itself authorize an artifact mutation/);
  assert.match(ask, /Route specialized requests without stealing ordinary conversation/);
  assert.match(ask, /A topic does\s+not become Claude Design merely because it could eventually be designed/);
  assert.match(ask, /Ordinary discussion, reflection, advice, critique, and chat/);
  assert.match(ask, /Codex-owned thread does not become\s+Claude-owned/i);
});

test("explicit Claude Design authoring includes the bounded source handoff", async () => {
  const design = await text("skills", "design", "SKILL.md");

  assert.match(design, /already authorizes the ordinary in-scope authoring\s+operations/);
  assert.match(design, /relevant\s+non-personal design files, tokens, components, assets, or source excerpts/);
  assert.match(design, /Do not interrupt the workflow to ask the user\s+to reconfirm/);
  assert.match(design, /never includes credentials, secrets, raw personal records/);
});
