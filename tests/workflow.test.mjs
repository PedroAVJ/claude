import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

const root = new URL("..", import.meta.url).pathname;

test("Oracle resolves named repositories from Developer while retaining old flag aliases", async () => {
  const dossier = await readFile(join(root, "skills", "oracle", "scripts", "oracle_dossier.py"), "utf8");
  assert.match(dossier, /DEFAULT_DEVELOPER_DIR = HOME \/ "Developer"/);
  assert.match(dossier, /Repo path or ~\/Developer repo name/);
  assert.match(dossier, /--all-developer-repos/);
  assert.match(dossier, /--developer-dir/);
  assert.match(dossier, /--all-desktop-repos/);
  assert.match(dossier, /--desktop-dir/);
  assert.doesNotMatch(dossier, /Desktop directory does not exist/);
});
