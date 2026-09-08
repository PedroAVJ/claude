#!/bin/sh
set -eu

label="com.pedro.claude-remote-control"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
plugin_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
template="$plugin_root/launchd/$label.plist.in"
support_dir="$HOME/Library/Application Support/Claude Remote Control"
logs_dir="$HOME/Library/Logs/Claude Remote Control"
agents_dir="$HOME/Library/LaunchAgents"
agent="$agents_dir/$label.plist"

python_bin=${CLAUDE_REMOTE_CONTROL_PYTHON:-$(command -v python3 || true)}
if [ -z "$python_bin" ] || [ ! -x "$python_bin" ]; then
  echo "Claude Remote Control: python3 is unavailable" >&2
  exit 1
fi

claude_bin=${CLAUDE_CODE_BIN:-$(command -v claude || true)}
if [ -z "$claude_bin" ] || [ ! -x "$claude_bin" ]; then
  echo "Claude Remote Control: Claude Code is unavailable or not executable" >&2
  exit 1
fi

if ! /usr/bin/codesign --verify --strict "$claude_bin" >/dev/null 2>&1; then
  echo "Claude Remote Control: Claude Code does not have a valid macOS code signature" >&2
  exit 1
fi
claude_identifier=$(/usr/bin/codesign -d --verbose=4 "$claude_bin" 2>&1 | /usr/bin/sed -n 's/^Identifier=//p')
if [ "$claude_identifier" != "com.anthropic.claude-code" ]; then
  echo "Claude Remote Control: expected Anthropic's signed native Claude Code binary; found identifier ${claude_identifier:-unsigned}" >&2
  exit 1
fi

workspace=${CLAUDE_REMOTE_CONTROL_WORKSPACE:-}
if [ -z "$workspace" ]; then
  echo "Set CLAUDE_REMOTE_CONTROL_WORKSPACE to the project directory for this service" >&2
  exit 1
fi
if [ ! -d "$workspace" ]; then
  echo "Claude Remote Control: workspace is unavailable: $workspace" >&2
  exit 1
fi

runtime_path="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
artifact=${CLAUDE_REMOTE_CONTROL_ARTIFACT:-1}
session_prefix=${CLAUDE_REMOTE_CONTROL_SESSION_PREFIX:-Mac}
permission_mode=${CLAUDE_REMOTE_CONTROL_PERMISSION_MODE:-default}
capacity=${CLAUDE_REMOTE_CONTROL_CAPACITY:-4}
debug_file=${CLAUDE_REMOTE_CONTROL_DEBUG_FILE:-$logs_dir/debug.log}

case "$capacity" in
  ''|*[!0-9]*)
    echo "Claude Remote Control: capacity must be an integer from 1 through 32" >&2
    exit 1
    ;;
esac
if [ "$capacity" -lt 1 ] || [ "$capacity" -gt 32 ]; then
  echo "Claude Remote Control: capacity must be between 1 and 32" >&2
  exit 1
fi

mkdir -p "$support_dir" "$logs_dir" "$agents_dir" "$(dirname -- "$debug_file")"
"$python_bin" "$script_dir/render-launch-agent.py" \
  --template "$template" \
  --output "$agent" \
  --claude "$claude_bin" \
  --workspace "$workspace" \
  --home "$HOME" \
  --path "$runtime_path" \
  --artifact "$artifact" \
  --session-prefix "$session_prefix" \
  --permission-mode "$permission_mode" \
  --capacity "$capacity" \
  --debug-file "$debug_file"

# Remove the pre-0.3.2 Python runtime wrapper after the direct plist exists.
rm -f -- "$support_dir/launcher.py"

domain="gui/$(id -u)"
launchctl bootout "$domain" "$agent" >/dev/null 2>&1 || true
launchctl bootstrap "$domain" "$agent"
launchctl kickstart -k "$domain/$label"
echo "Installed $label"
