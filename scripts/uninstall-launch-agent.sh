#!/bin/sh
set -eu

label="com.pedro.claude-remote-control"
agent="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"

launchctl bootout "$domain" "$agent" >/dev/null 2>&1 || true
rm -f -- "$agent" "$HOME/Library/Application Support/Claude Remote Control/launcher.py"
echo "Uninstalled $label; logs were retained"
