#!/usr/bin/env python3
"""
Create a small "oracle context" zip for handing a question off to another model/agent.

Design goals:
- Prefer git archive for deterministic tracked file selection.
- Default to packaging the entire tracked repository for external handoffs.
- Optionally include untracked files under selected paths.
- Always include an ORACLE_MANIFEST.txt inside the zip so the bundle is inspectable.
- Do not generate standalone prompt files by default; you can paste your original chat message
  (the question) alongside the zip in the target model.

This script intentionally does NOT try to "answer" the question. It only packages context.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_root() -> Path:
    proc = run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if proc.returncode != 0:
        raise RuntimeError(f"Not a git repository (git rev-parse failed): {proc.stderr.strip()}")
    return Path(proc.stdout.strip()).resolve()


def sanitize_name(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in value).strip("-")
    return cleaned or "repo"


def default_name(repo: Path, paths: list[str]) -> str:
    # Stable, project-based filename for whole-repo bundles.
    if not paths or paths == ["."]:
        return f"{sanitize_name(repo.name)}-repo"
    base = Path(paths[0]).name or "context"
    return sanitize_name(base)


def build_prompt_md(question: str, paths: list[str]) -> str:
    paths_block = "\n".join(f"- `{p}`" for p in paths) if paths else "- (entire tracked repository)"
    return textwrap.dedent(
        f"""\
        # Oracle Prompt

        ## Task

        {question.strip()}

        ## Included Context

        The zip contains repo files from these paths:
        {paths_block}

        ## Instructions

        - Do not assume missing files exist; base conclusions only on provided files.
        - If you need more context, list the specific file(s) or image(s) you would request next.
        - Provide a structured list of findings with evidence (file path + snippet/line refs where possible).
        """
    )


def should_exclude_from_zip(name: str) -> bool:
    # Keep this conservative: only drop common macOS zip noise.
    if name == ".DS_Store" or name.endswith("/.DS_Store"):
        return True
    if name.startswith("__MACOSX/"):
        return True
    return False


def strip_junk_entries(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, mode="r") as src:
        junk = [info.filename for info in src.infolist() if should_exclude_from_zip(info.filename)]
        if not junk:
            return

        tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")
        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                if should_exclude_from_zip(info.filename):
                    continue
                dst.writestr(info, src.read(info.filename))

    tmp_path.replace(zip_path)


def clear_directory_contents(dir_path: Path) -> None:
    if not dir_path.exists():
        return
    if not dir_path.is_dir():
        raise RuntimeError(f"Output path is not a directory: {dir_path}")
    for child in dir_path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Package minimal repo context into an oracle zip.")
    parser.add_argument(
        "--question",
        default="",
        help="Optional question text. Only used if --embed-prompt or --write-prompt-file is set.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help=(
            "Optional repo-relative paths (files or directories) to include via git archive. "
            "If omitted, package the entire tracked repository."
        ),
    )
    parser.add_argument(
        "--treeish",
        default="HEAD",
        help="Git tree-ish for git archive (default: HEAD).",
    )
    parser.add_argument(
        "--out-dir",
        default="oracle-out",
        help="Output directory (relative to repo root, or absolute). Default: oracle-out",
    )
    parser.add_argument(
        "--name",
        default="",
        help=(
            "Optional output zip base name. "
            "Defaults to '<repo-name>-repo' when packaging the whole repository."
        ),
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Also include untracked (non-ignored) files under the selected paths.",
    )
    parser.add_argument(
        "--include-diffs",
        action="store_true",
        help="Also include git status + diffs (working tree + staged) inside the zip.",
    )
    parser.add_argument(
        "--embed-prompt",
        action="store_true",
        help="Include ORACLE_PROMPT.md inside the zip (off by default).",
    )
    parser.add_argument(
        "--write-prompt-file",
        action="store_true",
        help="Also write an oracle-prompt-<name>.md next to the zip (off by default).",
    )
    args = parser.parse_args()

    repo = git_root()
    rel_paths = [p for p in args.paths if p]
    whole_repo = not rel_paths or rel_paths == ["."]
    name = sanitize_name(args.name.strip()) if args.name.strip() else default_name(repo, rel_paths)

    out_dir = (repo / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_directory_contents(out_dir)

    zip_path = out_dir / f"{name}.zip"
    prompt_path = out_dir / f"oracle-prompt-{name}.md"

    # 1) Create the base zip (tracked files only) using git archive.
    if whole_repo:
        archive_cmd = ["git", "archive", "--format=zip", f"--output={zip_path}", args.treeish]
    else:
        archive_cmd = ["git", "archive", "--format=zip", f"--output={zip_path}", args.treeish, "--", *rel_paths]
    proc = run(archive_cmd, cwd=repo)
    if proc.returncode != 0:
        raise RuntimeError(f"git archive failed:\n{proc.stderr.strip()}")

    prompt_md = ""
    if args.embed_prompt or args.write_prompt_file:
        if not args.question.strip():
            raise RuntimeError("--question is required when using --embed-prompt or --write-prompt-file")
        prompt_md = build_prompt_md(args.question, rel_paths)
        if args.write_prompt_file:
            prompt_path.write_text(prompt_md)

    # 2) Append optional extras (no manifest yet; we may strip junk entries first).
    with zipfile.ZipFile(zip_path, mode="a", compression=zipfile.ZIP_DEFLATED) as zf:
        if args.embed_prompt and prompt_md:
            zf.writestr("ORACLE_PROMPT.md", prompt_md)

        if args.include_diffs:
            status = run(["git", "status", "--porcelain=v1"], cwd=repo).stdout
            diff = run(["git", "diff"], cwd=repo).stdout
            diff_cached = run(["git", "diff", "--cached"], cwd=repo).stdout
            zf.writestr("ORACLE_GIT_STATUS.txt", status)
            zf.writestr("ORACLE_GIT_DIFF.patch", diff)
            zf.writestr("ORACLE_GIT_DIFF_CACHED.patch", diff_cached)

        if args.include_untracked:
            ls_cmd = ["git", "ls-files", "-z", "-o", "--exclude-standard"]
            if not whole_repo:
                ls_cmd.extend(["--", *rel_paths])
            ls = run(ls_cmd, cwd=repo)
            if ls.returncode == 0 and ls.stdout:
                existing = set(zf.namelist())
                for raw in ls.stdout.split("\0"):
                    if not raw:
                        continue
                    # Add file from working tree if it exists and isn't already in the archive.
                    if raw in existing:
                        continue
                    abs_path = (repo / raw).resolve()
                    if not abs_path.is_file():
                        continue
                    zf.write(abs_path, arcname=raw)

    strip_junk_entries(zip_path)

    with zipfile.ZipFile(zip_path, mode="a", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = "\n".join(sorted(set(zf.namelist()))) + "\n"
        zf.writestr("ORACLE_MANIFEST.txt", manifest)

    print(str(zip_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[oracle_pack] ERROR: {exc}", file=sys.stderr)
        raise
