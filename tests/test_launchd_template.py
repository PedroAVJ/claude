from __future__ import annotations

import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LaunchAgentTemplateTests(unittest.TestCase):
    def test_rendered_plist_has_stable_label_and_no_personal_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "agent.plist"
            home = root / "home with spaces"
            workspace = home / "Developer"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render-launch-agent.py"),
                    "--template",
                    str(ROOT / "launchd" / "com.pedro.claude-remote-control.plist.in"),
                    "--output",
                    str(output),
                    "--claude",
                    str(home / ".local/bin/claude"),
                    "--workspace",
                    str(workspace),
                    "--home",
                    str(home),
                    "--path",
                    "/usr/bin:/bin",
                    "--artifact",
                    "1",
                    "--session-prefix",
                    "the user-Mac",
                    "--permission-mode",
                    "bypassPermissions",
                    "--capacity",
                    "4",
                    "--debug-file",
                    str(home / "Library/Logs/Claude Remote Control/debug.log"),
                ],
                check=True,
            )
            data = plistlib.loads(output.read_bytes())
            self.assertEqual(data["Label"], "com.pedro.claude-remote-control")
            self.assertEqual(data["WorkingDirectory"], str(workspace))
            self.assertEqual(data["EnvironmentVariables"]["CLAUDE_CODE_ARTIFACT"], "1")
            self.assertEqual(data["ProgramArguments"][0], str(home / ".local/bin/claude"))
            self.assertEqual(data["ProgramArguments"][1], "remote-control")
            self.assertNotIn(sys.executable, data["ProgramArguments"])
            self.assertIn(str(home), output.read_text(encoding="utf-8"))
            self.assertNotIn(
                "example-user",
                (ROOT / "launchd" / "com.pedro.claude-remote-control.plist.in").read_text(
                    encoding="utf-8"
                ),
            )

    def test_artifact_setting_must_be_boolean_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render-launch-agent.py"),
                    "--template",
                    str(ROOT / "launchd" / "com.pedro.claude-remote-control.plist.in"),
                    "--output",
                    str(root / "agent.plist"),
                    "--claude",
                    str(root / "claude"),
                    "--workspace",
                    str(root / "Developer"),
                    "--home",
                    str(root),
                    "--path",
                    "/usr/bin:/bin",
                    "--artifact",
                    "yes",
                    "--session-prefix",
                    "the user-Mac",
                    "--permission-mode",
                    "bypassPermissions",
                    "--capacity",
                    "4",
                    "--debug-file",
                    str(root / "debug.log"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("artifact setting must be 0 or 1", result.stderr)

    def test_capacity_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render-launch-agent.py"),
                    "--template",
                    str(ROOT / "launchd" / "com.pedro.claude-remote-control.plist.in"),
                    "--output",
                    str(root / "agent.plist"),
                    "--claude",
                    str(root / "claude"),
                    "--workspace",
                    str(root / "Developer"),
                    "--home",
                    str(root),
                    "--path",
                    "/usr/bin:/bin",
                    "--artifact",
                    "1",
                    "--session-prefix",
                    "the user-Mac",
                    "--permission-mode",
                    "bypassPermissions",
                    "--capacity",
                    "100",
                    "--debug-file",
                    str(root / "debug.log"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("capacity must be between 1 and 32", result.stderr)


if __name__ == "__main__":
    unittest.main()
