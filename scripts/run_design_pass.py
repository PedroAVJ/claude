#!/usr/bin/env python3
import argparse
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from claude_host import (  # noqa: E402
    HostGuardError,
    ModelIdentityError,
    assert_foreign_host,
    assert_model_produced_output,
    claude_environment,
)


PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PLUGIN_ROOT / "templates" / "visual-handoff.md"
DEFAULT_LOG_ROOT = pathlib.Path.home() / ".local" / "share" / "claude-plugin" / "design-logs"
DEFAULT_MODEL = "claude-opus-5"


def extract_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "text_delta"} and item.get("text"):
                parts.append(item["text"])
            elif item.get("delta", {}).get("text"):
                parts.append(item["delta"]["text"])
        return "".join(parts)
    return ""


def print_event(event):
    event_type = event.get("type") or event.get("event")

    if event_type in {"assistant", "message"}:
        message = event.get("message", event)
        text = extract_text(message.get("content") or event.get("content"))
        if text:
            print(text, end="", flush=True)
        return

    if event_type in {"content_block_delta", "text_delta"}:
        text = event.get("delta", {}).get("text") or event.get("text")
        if text:
            print(text, end="", flush=True)
        return

    if event_type in {"tool_use", "tool_result"}:
        name = event.get("name") or event.get("tool_name") or event.get("id") or "tool"
        print(f"\n[claude:{event_type}] {name}", flush=True)
        return

    if event_type in {"error", "result"}:
        print(f"\n[claude:{event_type}] {event.get('subtype') or event.get('message') or ''}", flush=True)


def is_result_event(event):
    return (event.get("type") or event.get("event")) == "result"


def build_command(repo, debug_log, model, effort, prompt):
    cmd = [
        "claude",
        "-p",
        "--output-format=stream-json",
        "--include-partial-messages",
        "--verbose",
        "--no-chrome",
        "--no-session-persistence",
        "--debug-file",
        str(debug_log),
        "--add-dir",
        str(repo),
        "--permission-mode",
        "plan",
        "--tools",
        "Read,Glob,Grep,LS",
        "--effort",
        effort,
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


def main():
    parser = argparse.ArgumentParser(description="Run a streamed Claude visual-direction pass.")
    parser.add_argument("--repo", required=True, help="Repo path Claude may read.")
    parser.add_argument("--prompt-file", default="", help="Base prompt/template file.")
    parser.add_argument("--prompt", default="", help="Extra prompt appended after the prompt file.")
    parser.add_argument("--log-root", default=str(DEFAULT_LOG_ROOT), help="Directory for raw stream and debug logs.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model alias/name. Defaults to {DEFAULT_MODEL}.")
    parser.add_argument("--effort", default="medium", help="Claude effort level.")
    args = parser.parse_args()

    try:
        assert_foreign_host("claude:explain")
    except HostGuardError as error:
        print(f"[claude-run] refused: {error}", file=sys.stderr)
        return 2

    repo = pathlib.Path(args.repo).expanduser().resolve()
    prompt_file = args.prompt_file or str(DEFAULT_TEMPLATE)
    prompt_path = pathlib.Path(prompt_file).expanduser().resolve()
    log_root = pathlib.Path(args.log_root).expanduser().resolve()
    log_root.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw_log = log_root / f"{stamp}-stream.jsonl"
    debug_log = log_root / f"{stamp}-debug.log"

    prompt = prompt_path.read_text()
    if args.prompt:
        prompt = f"{prompt}\n\nProject-specific request:\n{args.prompt}\n"

    cmd = build_command(repo, debug_log, args.model, args.effort, prompt)

    print(f"[claude-run] repo: {repo}")
    print(f"[claude-run] codex plugin: {PLUGIN_ROOT}")
    print(f"[claude-run] stream log: {raw_log}")
    print(f"[claude-run] debug log: {debug_log}")
    print()

    process = subprocess.Popen(
        cmd,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=claude_environment(),
    )

    final_result = None
    with raw_log.open("w") as raw:
        assert process.stdout is not None
        for line in process.stdout:
            raw.write(line)
            raw.flush()
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                print(stripped, flush=True)
                continue
            if is_result_event(event):
                final_result = event
            print_event(event)

    return_code = process.wait()
    print(f"\n[claude-run] exit code: {return_code}")

    if return_code != 0:
        return return_code

    # A clean exit is not proof the requested model answered. Verify before the
    # caller treats this pass as an Opus 5 visual-direction response.
    if final_result is None:
        print(
            "[claude-run] refused: the stream carried no result event, so the "
            "answering model cannot be verified.",
            file=sys.stderr,
        )
        return 3

    try:
        assert_model_produced_output(final_result.get("modelUsage"), args.model)
    except ModelIdentityError as error:
        print(f"[claude-run] refused: {error}", file=sys.stderr)
        return 3

    print(f"[claude-run] verified: {args.model} produced this pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
