#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { basename, join, relative, resolve, sep } from "node:path";

function fail(message) {
  throw new Error(message);
}

async function filesBelow(root, current = root) {
  const result = [];
  for (const entry of await readdir(current, { withFileTypes: true })) {
    const path = join(current, entry.name);
    if (entry.isDirectory()) result.push(...await filesBelow(root, path));
    else if (entry.isFile()) result.push(relative(root, path).split(sep).join("/"));
  }
  return result.sort();
}

function assertProject(manifest, directory) {
  if (manifest.schemaVersion !== 1) fail("project.json must use schemaVersion 1");
  const project = manifest.project;
  if (!project || typeof project !== "object") fail("project metadata is required");
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(project.id || "")) {
    fail("project.id must be a UUID");
  }
  if (basename(directory) !== project.id) {
    fail(`snapshot directory ${basename(directory)} does not match project.id ${project.id}`);
  }
  if (!/^https:\/\/claude\.ai\/design\/p\//.test(project.url || "")) {
    fail("project.url must be a durable claude.ai/design project URL");
  }
  if (!Array.isArray(manifest.files) || !Array.isArray(manifest.excluded)) {
    fail("project.json must contain files and excluded arrays");
  }
}

function safeRelativePath(path) {
  return typeof path === "string" && path.length > 0 &&
    !path.startsWith("/") && !path.split("/").includes("..");
}

async function validate(directory) {
  const root = resolve(directory);
  const manifest = JSON.parse(await readFile(join(root, "project.json"), "utf8"));
  assertProject(manifest, root);

  const seen = new Set();
  const expected = [];
  for (const file of manifest.files) {
    if (!safeRelativePath(file.path)) fail(`unsafe file path: ${file.path}`);
    if (seen.has(file.path)) fail(`duplicate manifest path: ${file.path}`);
    seen.add(file.path);
    if (!Number.isInteger(file.size) || file.size < 0) fail(`invalid size: ${file.path}`);
    if (!/^[0-9a-f]{64}$/.test(file.sha256 || "")) fail(`invalid sha256: ${file.path}`);

    const diskPath = join(root, "files", ...file.path.split("/"));
    const diskStat = await stat(diskPath).catch(() => null);
    if (!diskStat?.isFile()) fail(`missing mirrored file: ${file.path}`);
    if (diskStat.size !== file.size) {
      fail(`size mismatch for ${file.path}: expected ${file.size}, found ${diskStat.size}`);
    }
    const digest = createHash("sha256").update(await readFile(diskPath)).digest("hex");
    if (digest !== file.sha256) fail(`sha256 mismatch for ${file.path}`);
    expected.push(file.path);
  }

  for (const excluded of manifest.excluded) {
    if (!safeRelativePath(excluded.path)) fail(`unsafe excluded path: ${excluded.path}`);
    if (seen.has(excluded.path)) fail(`path is both mirrored and excluded: ${excluded.path}`);
    if (typeof excluded.reason !== "string" || !excluded.reason) {
      fail(`missing exclusion reason: ${excluded.path}`);
    }
    seen.add(excluded.path);
  }

  const actual = await filesBelow(join(root, "files")).catch(() => []);
  const unmanifested = actual.filter((path) => !expected.includes(path));
  if (unmanifested.length) fail(`unmanifested mirrored files: ${unmanifested.join(", ")}`);

  return { project: manifest.project.id, files: expected.length, excluded: manifest.excluded.length };
}

const directory = process.argv[2];
if (!directory) {
  console.error("Usage: validate-design-snapshot.mjs <snapshot-directory>");
  process.exit(2);
}

try {
  console.log(JSON.stringify(await validate(directory)));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
