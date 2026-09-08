#!/usr/bin/env python3
"""
Build a single static Oracle dossier zip for external model handoffs.

The zip is meant to be uploaded to a model that cannot call tools. It contains:
- an optional task prompt,
- optional project/custom instructions,
- a thread summary,
- repo snapshots,
- optional exported connector/context files,
- a JSON manifest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HOME = Path.home()
DEFAULT_DEVELOPER_DIR = HOME / "Developer"
DEFAULT_OUT_DIR = "oracle-out"

SKIP_DIR_NAMES = {
    ".cache",
    ".git",
    ".next",
    ".nuxt",
    ".parcel-cache",
    ".pytest_cache",
    ".turbo",
    ".venv",
    "__pycache__",
    "coverage",
    "node_modules",
    "venv",
}

SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "service-account.json",
    "service_account.json",
    "firebase-service-account.json",
    "firebase_service_account.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}

SENSITIVE_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
}

REPO_ALIASES = {
    "pingo": "pinggo",
}


@dataclass
class SkippedFile:
    source: str
    path: str
    reason: str


@dataclass
class RepoRecord:
    name: str
    path: str
    branch: str | None
    commit: str | None
    remote: str | None
    snapshot: str
    tracked_files_added: int = 0
    untracked_files_added: int = 0
    dirty: bool = False
    skipped: list[SkippedFile] = field(default_factory=list)


@dataclass
class ExternalRecord:
    label: str
    source_path: str
    target_path: str
    files_added: int
    skipped: list[SkippedFile] = field(default_factory=list)


def run(
    cmd: list[str],
    cwd: Path,
    *,
    text: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.strip() if isinstance(proc.stderr, str) else proc.stderr.decode(errors="replace")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{stderr}")
    return proc


def sanitize_name(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "oracle-dossier"


def read_text_arg(value: str, file_path: str, *, fallback: str) -> str:
    if file_path:
        return Path(file_path).expanduser().read_text(encoding="utf-8").strip()
    if value:
        return value.strip()
    return fallback


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


def ensure_safe_output_dir(out_dir: Path) -> None:
    protected = {
        Path("/").resolve(),
        HOME.resolve(),
        DEFAULT_DEVELOPER_DIR.resolve(),
        Path.cwd().resolve(),
    }
    if out_dir in protected:
        raise RuntimeError(f"Refusing to clear protected output directory: {out_dir}")
    if out_dir.name in {"", ".", ".."}:
        raise RuntimeError(f"Refusing unsafe output directory: {out_dir}")


def is_sensitive_or_junk_path(rel_path: str) -> str | None:
    normalized = rel_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    lowered_parts = [part.lower() for part in parts]
    if any(part in SKIP_DIR_NAMES for part in lowered_parts):
        return "generated or dependency directory"

    if not parts:
        return None

    basename = parts[-1]
    lower_basename = basename.lower()

    if lower_basename == ".ds_store" or normalized.startswith("__MACOSX/"):
        return "platform metadata"
    if lower_basename in SENSITIVE_FILE_NAMES:
        return "sensitive filename"
    if lower_basename.startswith(".env."):
        return "environment file"
    if any(lower_basename.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
        return "sensitive file suffix"
    if lower_basename.endswith(".sqlite") or lower_basename.endswith(".sqlite3") or lower_basename.endswith(".db"):
        return "local database file"

    return None


def resolve_repo(repo_arg: str, developer_dir: Path) -> Path:
    alias = REPO_ALIASES.get(repo_arg, repo_arg)
    raw_path = Path(alias).expanduser()

    candidates: list[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append((Path.cwd() / raw_path).resolve())
        candidates.append((developer_dir / raw_path).resolve())

    for candidate in candidates:
        if candidate.exists():
            proc = run(["git", "rev-parse", "--show-toplevel"], cwd=candidate)
            if proc.returncode == 0:
                return Path(proc.stdout.strip()).resolve()

    raise RuntimeError(f"Could not resolve git repo: {repo_arg}")


def discover_developer_repos(developer_dir: Path) -> list[Path]:
    repos: list[Path] = []
    if not developer_dir.exists():
        raise RuntimeError(f"Developer directory does not exist: {developer_dir}")

    for child in sorted(developer_dir.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        proc = run(["git", "rev-parse", "--show-toplevel"], cwd=child)
        if proc.returncode != 0:
            continue
        root = Path(proc.stdout.strip()).resolve()
        if root == child.resolve() and root not in repos:
            repos.append(root)
    return repos


def git_output(repo: Path, cmd: list[str]) -> str | None:
    proc = run(cmd, cwd=repo)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def repo_git_info(repo: Path, snapshot: str) -> dict[str, Any]:
    status = git_output(repo, ["git", "status", "--porcelain=v1"]) or ""
    return {
        "path": str(repo),
        "branch": git_output(repo, ["git", "branch", "--show-current"]),
        "commit": git_output(repo, ["git", "rev-parse", "HEAD"]),
        "remote": git_output(repo, ["git", "remote", "get-url", "origin"]),
        "snapshot": snapshot,
        "dirty": bool(status),
    }


def list_head_files(repo: Path, treeish: str) -> list[str]:
    proc = run(["git", "ls-tree", "-rz", "--name-only", treeish], cwd=repo, text=False, check=True)
    stdout = proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode()
    return [item.decode("utf-8", errors="replace") for item in stdout.split(b"\0") if item]


def list_worktree_tracked_files(repo: Path) -> list[str]:
    proc = run(["git", "ls-files", "-z"], cwd=repo, text=False, check=True)
    stdout = proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode()
    return [item.decode("utf-8", errors="replace") for item in stdout.split(b"\0") if item]


def list_untracked_files(repo: Path) -> list[str]:
    proc = run(["git", "ls-files", "-z", "-o", "--exclude-standard"], cwd=repo, text=False, check=True)
    stdout = proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode()
    return [item.decode("utf-8", errors="replace") for item in stdout.split(b"\0") if item]


def git_show_file(repo: Path, treeish: str, rel_path: str) -> bytes | None:
    proc = run(["git", "show", f"{treeish}:{rel_path}"], cwd=repo, text=False)
    if proc.returncode != 0:
        return None
    return proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode()


def write_bytes_file(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def copy_file_with_filters(
    source_file: Path,
    target_file: Path,
    *,
    source_label: str,
    rel_label: str,
    max_file_bytes: int | None,
    skipped: list[SkippedFile],
) -> bool:
    reason = is_sensitive_or_junk_path(rel_label)
    if reason:
        skipped.append(SkippedFile(source=source_label, path=rel_label, reason=reason))
        return False
    try:
        size = source_file.stat().st_size
    except FileNotFoundError:
        skipped.append(SkippedFile(source=source_label, path=rel_label, reason="file not found"))
        return False
    if max_file_bytes is not None and size > max_file_bytes:
        skipped.append(SkippedFile(source=source_label, path=rel_label, reason=f"larger than {max_file_bytes} bytes"))
        return False
    target_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, target_file)
    return True


def add_repo_snapshot(
    repo: Path,
    stage_root: Path,
    *,
    treeish: str,
    snapshot: str,
    include_diffs: bool,
    include_untracked: bool,
    max_file_bytes: int | None,
) -> RepoRecord:
    info = repo_git_info(repo, snapshot)
    repo_name = sanitize_name(repo.name)
    target_root = stage_root / "context" / "repos" / repo_name
    skipped: list[SkippedFile] = []
    tracked_added = 0
    untracked_added = 0

    files = list_head_files(repo, treeish) if snapshot == "head" else list_worktree_tracked_files(repo)

    for rel_path in files:
        reason = is_sensitive_or_junk_path(rel_path)
        if reason:
            skipped.append(SkippedFile(source=repo_name, path=rel_path, reason=reason))
            continue

        target_file = target_root / rel_path
        if snapshot == "head":
            data = git_show_file(repo, treeish, rel_path)
            if data is None:
                skipped.append(SkippedFile(source=repo_name, path=rel_path, reason="not a file in git tree"))
                continue
            if max_file_bytes is not None and len(data) > max_file_bytes:
                skipped.append(SkippedFile(source=repo_name, path=rel_path, reason=f"larger than {max_file_bytes} bytes"))
                continue
            write_bytes_file(target_file, data)
        else:
            source_file = repo / rel_path
            copied = copy_file_with_filters(
                source_file,
                target_file,
                source_label=repo_name,
                rel_label=rel_path,
                max_file_bytes=max_file_bytes,
                skipped=skipped,
            )
            if not copied:
                continue
        tracked_added += 1

    if include_untracked:
        for rel_path in list_untracked_files(repo):
            source_file = repo / rel_path
            target_file = target_root / rel_path
            copied = copy_file_with_filters(
                source_file,
                target_file,
                source_label=repo_name,
                rel_label=rel_path,
                max_file_bytes=max_file_bytes,
                skipped=skipped,
            )
            if copied:
                untracked_added += 1

    oracle_dir = target_root / "_oracle"
    oracle_dir.mkdir(parents=True, exist_ok=True)
    (oracle_dir / "REPO_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if include_diffs:
        (oracle_dir / "GIT_STATUS.txt").write_text(
            git_output(repo, ["git", "status", "--porcelain=v1"]) or "",
            encoding="utf-8",
        )
        (oracle_dir / "GIT_DIFF.patch").write_text(
            git_output(repo, ["git", "diff"]) or "",
            encoding="utf-8",
        )
        (oracle_dir / "GIT_DIFF_CACHED.patch").write_text(
            git_output(repo, ["git", "diff", "--cached"]) or "",
            encoding="utf-8",
        )

    (oracle_dir / "SKIPPED_FILES.json").write_text(
        json.dumps([item.__dict__ for item in skipped], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return RepoRecord(
        name=repo_name,
        path=str(repo),
        branch=info["branch"],
        commit=info["commit"],
        remote=info["remote"],
        snapshot=snapshot,
        tracked_files_added=tracked_added,
        untracked_files_added=untracked_added,
        dirty=bool(info["dirty"]),
        skipped=skipped,
    )


def parse_labeled_path(value: str) -> tuple[str, Path]:
    if "=" in value:
        label, raw_path = value.split("=", 1)
        return sanitize_name(label), Path(raw_path).expanduser().resolve()
    path = Path(value).expanduser().resolve()
    return sanitize_name(path.stem or path.name), path


def add_external_file(
    value: str,
    stage_root: Path,
    *,
    max_file_bytes: int | None,
) -> ExternalRecord:
    label, source = parse_labeled_path(value)
    if not source.is_file():
        raise RuntimeError(f"External context file does not exist: {source}")
    target = stage_root / "context" / "external" / label / source.name
    skipped: list[SkippedFile] = []
    copied = copy_file_with_filters(
        source,
        target,
        source_label=label,
        rel_label=source.name,
        max_file_bytes=max_file_bytes,
        skipped=skipped,
    )
    return ExternalRecord(
        label=label,
        source_path=str(source),
        target_path=str(target.relative_to(stage_root)),
        files_added=1 if copied else 0,
        skipped=skipped,
    )


def add_external_dir(
    value: str,
    stage_root: Path,
    *,
    max_file_bytes: int | None,
) -> ExternalRecord:
    label, source = parse_labeled_path(value)
    if not source.is_dir():
        raise RuntimeError(f"External context directory does not exist: {source}")

    target_root = stage_root / "context" / "external" / label
    skipped: list[SkippedFile] = []
    files_added = 0

    for source_file in sorted(source.rglob("*")):
        if not source_file.is_file():
            continue
        rel_path = source_file.relative_to(source).as_posix()
        target_file = target_root / rel_path
        copied = copy_file_with_filters(
            source_file,
            target_file,
            source_label=label,
            rel_label=rel_path,
            max_file_bytes=max_file_bytes,
            skipped=skipped,
        )
        if copied:
            files_added += 1

    return ExternalRecord(
        label=label,
        source_path=str(source),
        target_path=str(target_root.relative_to(stage_root)),
        files_added=files_added,
        skipped=skipped,
    )


def parse_note(value: str) -> tuple[str, str]:
    if "=" in value:
        label, text = value.split("=", 1)
        return sanitize_name(label), text.strip()
    return "note", value.strip()


def default_custom_instructions() -> str:
    return """# Oracle Custom Instructions

You are analyzing a static context dossier uploaded as a zip file.

Ground your answer in the uploaded files. Cite paths from the dossier when making factual claims. Do not assume access to GitHub, MCP servers, Notion, WhatsApp, Gmail, Linear, shells, browsers, databases, deployments, or other live tools.

If the task would normally require side effects, do not claim you performed them. Instead, provide the exact patch, reply, plan, query, or checklist the user can hand back to Codex.

Separate confirmed facts from inferences. If context is missing, say exactly what additional file, export, screenshot, or source would resolve the uncertainty.

Prefer a concise answer with enough evidence to be actionable. When reviewing code, lead with bugs, risks, regressions, and missing tests.
"""


def build_prompt(task: str) -> str:
    return f"""# Oracle Prompt

## Task

{task}

## How To Use The Dossier

Read `ORACLE_README.md` first, then inspect the files under `context/`.

Use `ORACLE_MANIFEST.json` to understand what sources were included and what was skipped.

Answer the task using only this uploaded context and clearly state when a conclusion is inferred rather than directly evidenced.
"""


def build_thread_summary(thread_summary: str) -> str:
    return f"""# Thread Summary

{thread_summary}
"""


def build_readme(
    *,
    created_at: str,
    task: str,
    repo_records: list[RepoRecord],
    external_records: list[ExternalRecord],
    context_only: bool = False,
) -> str:
    repo_lines = "\n".join(
        f"- `context/repos/{repo.name}/`: {repo.snapshot} snapshot from `{repo.path}`"
        for repo in repo_records
    ) or "- No repos were included."

    external_lines = "\n".join(
        f"- `context/external/{record.label}/`: exported context from `{record.source_path}`"
        for record in external_records
    ) or "- No external connector/context exports were included."

    if context_only:
        task_preview = "No embedded prompt. This is a context-only upload bundle; the user will drive the conversation."
        start_here = """1. Use `ORACLE_MANIFEST.json` as the inventory.
2. Inspect `context/thread/THREAD_SUMMARY.md` if prior conversation context matters.
3. Inspect the relevant repo and external context folders.
4. Follow the user's live chat instructions; no task prompt is embedded in this zip."""
    else:
        task_preview = task.strip().replace("\n", " ")
        if len(task_preview) > 500:
            task_preview = task_preview[:497] + "..."
        start_here = """1. Read `ORACLE_PROMPT.md`.
2. Follow `ORACLE_CUSTOM_INSTRUCTIONS.md`.
3. Use `ORACLE_MANIFEST.json` as the inventory.
4. Inspect `context/thread/THREAD_SUMMARY.md`.
5. Inspect the relevant repo and external context folders."""

    return f"""# Oracle Dossier

Created at: {created_at}

This zip is a static context bundle for a model that cannot call live tools.

## Task Preview

{task_preview}

## Start Here

{start_here}

## Included Repos

{repo_lines}

## Included External Context

{external_lines}

## Important Boundary

The model receiving this zip cannot fetch missing context, run commands, update services, or perform side effects. It should use this upload as static context for the user's live conversation.
"""


def collect_stage_files(stage_root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(stage_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(stage_root).as_posix()
        files.append({"path": rel, "size_bytes": path.stat().st_size})
    return files


def zip_stage(stage_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(stage_root).as_posix()
            if is_sensitive_or_junk_path(rel):
                continue
            zf.write(path, arcname=rel)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a single Oracle dossier zip.")
    parser.add_argument("--task", default="", help="Question or task for the Oracle model.")
    parser.add_argument("--task-file", default="", help="Markdown/text file containing the Oracle task.")
    parser.add_argument("--thread-summary", default="", help="Brief summary of the current Codex thread.")
    parser.add_argument("--thread-summary-file", default="", help="Markdown/text file containing the thread summary.")
    parser.add_argument("--repo", action="append", default=[], help="Repo path or ~/Developer repo name. Repeatable.")
    parser.add_argument("--all-developer-repos", "--all-desktop-repos", dest="all_developer_repos", action="store_true", help="Include every immediate git repo under --developer-dir.")
    parser.add_argument("--developer-dir", "--desktop-dir", dest="developer_dir", default=str(DEFAULT_DEVELOPER_DIR), help="Directory used for named repo resolution.")
    parser.add_argument("--context-file", action="append", default=[], help="External context file, optionally label=/path/file.md.")
    parser.add_argument("--context-dir", action="append", default=[], help="External context directory, optionally label=/path/dir.")
    parser.add_argument("--note", action="append", default=[], help="Inline external note, optionally label=text.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory relative to current cwd, or absolute.")
    parser.add_argument("--name", default="", help="Zip basename. Defaults to oracle-dossier-YYYYmmdd-HHMMSS.")
    parser.add_argument("--snapshot", choices=["head", "worktree"], default="head", help="Repo snapshot source.")
    parser.add_argument("--treeish", default="HEAD", help="Git tree-ish used when --snapshot=head.")
    parser.add_argument("--include-diffs", action="store_true", help="Include git status and patch files under each repo _oracle folder.")
    parser.add_argument("--include-untracked", action="store_true", help="Include non-ignored untracked files from selected repos.")
    parser.add_argument("--max-file-mb", type=float, default=25.0, help="Skip individual files larger than this. Use 0 for no cap.")
    parser.add_argument("--keep-stage", action="store_true", help="Keep the temporary expanded dossier folder next to the zip.")
    parser.add_argument("--context-only", action="store_true", help="Build a context-only bundle without ORACLE_PROMPT.md or ORACLE_CUSTOM_INSTRUCTIONS.md.")
    args = parser.parse_args()

    task = read_text_arg(
        args.task,
        args.task_file,
        fallback="No explicit Oracle task was provided. Use the surrounding chat message as the task.",
    )
    thread_summary = read_text_arg(
        args.thread_summary,
        args.thread_summary_file,
        fallback="No thread summary was provided. Ask Codex for a refreshed summary if prior conversation context matters.",
    )

    developer_dir = Path(args.developer_dir).expanduser().resolve()
    max_file_bytes = None if args.max_file_mb <= 0 else int(args.max_file_mb * 1024 * 1024)
    created_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    default_name = f"oracle-dossier-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    name = sanitize_name(args.name) if args.name else default_name

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    out_dir = out_dir.resolve()
    ensure_safe_output_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_directory_contents(out_dir)

    stage_root = out_dir / f".{name}-stage"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True)

    repo_paths: list[Path] = []
    if args.all_developer_repos:
        repo_paths.extend(discover_developer_repos(developer_dir))
    for repo_arg in args.repo:
        repo_paths.append(resolve_repo(repo_arg, developer_dir))

    deduped_repo_paths: list[Path] = []
    seen_repos: set[Path] = set()
    for repo in repo_paths:
        if repo not in seen_repos:
            deduped_repo_paths.append(repo)
            seen_repos.add(repo)

    repo_records: list[RepoRecord] = []
    external_records: list[ExternalRecord] = []

    for repo in deduped_repo_paths:
        repo_records.append(
            add_repo_snapshot(
                repo,
                stage_root,
                treeish=args.treeish,
                snapshot=args.snapshot,
                include_diffs=args.include_diffs,
                include_untracked=args.include_untracked,
                max_file_bytes=max_file_bytes,
            )
        )

    for context_file in args.context_file:
        external_records.append(add_external_file(context_file, stage_root, max_file_bytes=max_file_bytes))

    for context_dir in args.context_dir:
        external_records.append(add_external_dir(context_dir, stage_root, max_file_bytes=max_file_bytes))

    for raw_note in args.note:
        label, text = parse_note(raw_note)
        target = stage_root / "context" / "external" / label / "NOTE.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {label}\n\n{text}\n", encoding="utf-8")
        external_records.append(
            ExternalRecord(
                label=label,
                source_path="inline note",
                target_path=str(target.relative_to(stage_root)),
                files_added=1,
            )
        )

    (stage_root / "context" / "thread").mkdir(parents=True, exist_ok=True)
    (stage_root / "context" / "thread" / "THREAD_SUMMARY.md").write_text(
        build_thread_summary(thread_summary),
        encoding="utf-8",
    )
    if not args.context_only:
        (stage_root / "ORACLE_PROMPT.md").write_text(build_prompt(task), encoding="utf-8")
        (stage_root / "ORACLE_CUSTOM_INSTRUCTIONS.md").write_text(default_custom_instructions(), encoding="utf-8")

    skipped_files = []
    for repo in repo_records:
        skipped_files.extend(item.__dict__ for item in repo.skipped)
    for external in external_records:
        skipped_files.extend(item.__dict__ for item in external.skipped)

    manifest = {
        "created_at": created_at,
        "task_provided": bool(args.task or args.task_file),
        "context_only": args.context_only,
        "thread_summary_provided": bool(args.thread_summary or args.thread_summary_file),
        "snapshot": args.snapshot,
        "treeish": args.treeish,
        "include_diffs": args.include_diffs,
        "include_untracked": args.include_untracked,
        "max_file_bytes": max_file_bytes,
        "repos": [
            {
                "name": repo.name,
                "path": repo.path,
                "branch": repo.branch,
                "commit": repo.commit,
                "remote": repo.remote,
                "snapshot": repo.snapshot,
                "tracked_files_added": repo.tracked_files_added,
                "untracked_files_added": repo.untracked_files_added,
                "dirty": repo.dirty,
                "skipped_count": len(repo.skipped),
            }
            for repo in repo_records
        ],
        "external_context": [
            {
                "label": external.label,
                "source_path": external.source_path,
                "target_path": external.target_path,
                "files_added": external.files_added,
                "skipped_count": len(external.skipped),
            }
            for external in external_records
        ],
        "skipped_files": skipped_files,
        "files": [],
    }

    (stage_root / "ORACLE_README.md").write_text(
        build_readme(
            created_at=created_at,
            task=task,
            repo_records=repo_records,
            external_records=external_records,
            context_only=args.context_only,
        ),
        encoding="utf-8",
    )

    manifest["files"] = collect_stage_files(stage_root)
    (stage_root / "ORACLE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    zip_path = out_dir / f"{name}.zip"
    zip_stage(stage_root, zip_path)

    if not args.keep_stage:
        shutil.rmtree(stage_root)

    print(str(zip_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[oracle_dossier] ERROR: {exc}", file=sys.stderr)
        raise
