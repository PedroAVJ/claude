import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "oracle"
SKILL_PATH = SKILL_ROOT / "SKILL.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FableOracleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = SKILL_PATH.read_text(encoding="utf-8")
        self.codex_manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.oracle_fable = _load(
            "oracle_fable", SKILL_ROOT / "scripts" / "oracle_fable.py"
        )

    def test_release_version(self) -> None:
        self.assertEqual(self.codex_manifest["version"], "0.5.21")

    def test_fable_is_the_only_oracle_model(self) -> None:
        for text in (
            self.skill,
            (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8"),
            self.codex_manifest["description"],
        ):
            self.assertIn("Fable 5.1", text)
        self.assertIn("Fable 5.1 is the only Oracle model", self.skill)

    def test_fable_invocation_is_explicit_and_ephemeral(self) -> None:
        for required in (
            "--model claude-fable-5-1",
            "--effort max",
            "CLAUDE_CODE_NO_MODEL_FALLBACK=1",
            "--tools ''",
            "--output-format json",
            "--no-session-persistence",
            "claude-fable-5-1",
        ):
            self.assertIn(required, self.skill)
        self.assertIn("canonical identifier", self.skill)
        self.assertIn("explicit max effort", self.skill.lower())
        self.assertIn("\n  --effort max", self.skill)
        self.assertNotIn("\n  --model fable", self.skill)

    def test_helper_requests_fable_max(self) -> None:
        source = (SKILL_ROOT / "scripts" / "oracle_fable.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('FABLE_EFFORT = "max"', source)
        self.assertIn('"--effort",', source)
        self.assertIn("FABLE_EFFORT", source)

    def test_fable_identity_guard_is_fail_closed(self) -> None:
        valid_fable = {
            "is_error": False,
            "result": "answer",
            "modelUsage": {
                "fable": {"canonicalModel": "claude-fable-5-1", "outputTokens": 900}
            },
        }
        valid_with_auxiliary = {
            "is_error": False,
            "result": "answer",
            "modelUsage": {
                "helper": {
                    "canonicalModel": "claude-haiku-4-5-20251001",
                    "outputTokens": 16,
                },
                "fable": {"canonicalModel": "claude-fable-5-1", "outputTokens": 10},
            },
        }
        opus_only = {
            "is_error": False,
            "result": "answer",
            "modelUsage": {
                "helper": {
                    "canonicalModel": "claude-haiku-4-5-20251001",
                    "outputTokens": 16,
                },
                "opus": {"canonicalModel": "claude-opus-5", "outputTokens": 900},
            },
        }
        fable_and_opus = {
            "is_error": False,
            "result": "answer",
            "modelUsage": {
                "fable": {"canonicalModel": "claude-fable-5-1", "outputTokens": 900},
                "opus": {"canonicalModel": "claude-opus-5", "outputTokens": 1},
            },
        }

        self.oracle_fable.validate_fable_result(valid_fable)
        self.oracle_fable.validate_fable_result(valid_with_auxiliary)
        with self.assertRaises(self.oracle_fable.FableValidationError):
            self.oracle_fable.validate_fable_result(opus_only)
        with self.assertRaises(self.oracle_fable.FableValidationError):
            self.oracle_fable.validate_fable_result(fable_and_opus)

    def test_failure_returns_no_oracle_answer(self) -> None:
        self.assertIn("Oracle did not produce an answer", self.skill)
        self.assertIn("do not return an Oracle answer", self._agent_yaml())
        self.assertIn("Do not silently", self.skill)

    def test_neutral_icon_exists_and_is_referenced(self) -> None:
        self.assertTrue((SKILL_ROOT / "assets" / "oracle-icon.svg").is_file())
        self.assertIn("./assets/oracle-icon.svg", self._agent_yaml())

    def _agent_yaml(self) -> str:
        return (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")


class HostScopingTests(unittest.TestCase):
    """Host-to-host scripts must remain unreachable from Claude Code."""

    def setUp(self) -> None:
        self.claude_host = _load(
            "claude_host", PLUGIN_ROOT / "scripts" / "claude_host.py"
        )

    def test_dual_client_manifest_keeps_the_runtime_guard(self) -> None:
        codex_manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        claude_manifest = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("claude", codex_manifest["name"])
        self.assertEqual(codex_manifest["name"], claude_manifest["name"])
        self.assertEqual(codex_manifest["version"], claude_manifest["version"])
        self.assertIn(
            "CLAUDECODE",
            (PLUGIN_ROOT / "scripts" / "claude_host.py").read_text(),
        )

    def test_host_guard_fires_inside_claude_code(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            with self.assertRaises(self.claude_host.HostGuardError):
                self.claude_host.assert_foreign_host("oracle")

    def test_host_guard_allows_codex(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.claude_host.assert_foreign_host("oracle")

    def test_oracle_helper_refuses_inside_claude_code(self) -> None:
        oracle_fable = _load(
            "oracle_fable_guard", SKILL_ROOT / "scripts" / "oracle_fable.py"
        )
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.assertEqual(2, oracle_fable.main())


if __name__ == "__main__":
    unittest.main()
