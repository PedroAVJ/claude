import importlib.util
import os
import pathlib
import sys
import unittest
from unittest import mock


SCRIPT_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "run_design_pass.py"
PLUGIN_ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("run_design_pass", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BuildCommandTests(unittest.TestCase):
    def test_frontend_implementation_surface_is_removed(self):
        self.assertFalse(
            (PLUGIN_ROOT / "skills" / "frontend-ui" / "SKILL.md").exists()
        )
        self.assertFalse(
            (PLUGIN_ROOT / "templates" / "frontend-implementation.md").exists()
        )
        self.assertFalse((PLUGIN_ROOT / "templates" / "frontend-handoff.md").exists())
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("acceptEdits", source)
        self.assertNotIn('"implement"', source)

    def test_visual_mode_is_read_only_and_defaults_to_canonical_opus_5(self):
        command = MODULE.build_command(
            pathlib.Path("/tmp/repo"),
            pathlib.Path("/tmp/debug.log"),
            MODULE.DEFAULT_MODEL,
            "medium",
            "prompt",
        )

        self.assertEqual("claude-opus-5", MODULE.DEFAULT_MODEL)
        self.assertEqual("plan", command[command.index("--permission-mode") + 1])
        self.assertEqual("Read,Glob,Grep,LS", command[command.index("--tools") + 1])
        self.assertIn("--no-session-persistence", command)
        self.assertEqual(
            "claude-opus-5", command[command.index("--model") + 1]
        )

    def test_design_pass_refuses_to_run_inside_claude_code(self):
        argv = ["run_design_pass.py", "--repo", "/tmp/repo"]
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
                # Must refuse before spawning anything; a nested Claude Code call
                # would ask the running model to second-opinion itself.
                self.assertEqual(2, MODULE.main())

    def test_design_pass_disables_model_fallback(self):
        environment = MODULE.claude_environment()
        self.assertEqual("1", environment["CLAUDE_CODE_NO_MODEL_FALLBACK"])


if __name__ == "__main__":
    unittest.main()
