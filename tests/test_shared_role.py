import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedRoleTests(unittest.TestCase):
    def setUp(self):
        self.relay = load("role_relay", ROOT / "skills/claude/scripts/ask_fable.py")
        self.roles = __import__("shared_role")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def contract(self, key="test_reader", **changes):
        config = {"model": "some-other-model", "model_reasoning_effort": "low",
                  "developer_instructions": "Preserve source names exactly.", "agents": {"enabled": False}}
        config.update(changes)
        path = self.root / (key + ".json")
        path.write_text(json.dumps({"registry_file": "/private/registry.toml", "merges_config_layers": False,
                                    "role": {"key": key, "description": "Reads a bounded source", "config": config}}))
        return path

    def prepare(self, path, delegates=None):
        return self.roles.prepare_role(path, delegates or [], model=self.relay.FABLE_MODEL, default_effort="high")

    def test_individual_role_preserves_effort_instructions_and_fable_identity(self):
        role = self.prepare(self.contract())
        with mock.patch.object(self.relay.shutil, "which", return_value="/bin/claude"):
            command = self.relay._command("session", False, role)
        self.assertEqual("low", command[command.index("--effort") + 1])
        self.assertEqual("claude-fable-5-1", command[command.index("--model") + 1])
        self.assertIn("Preserve source names exactly.", command[command.index("--append-system-prompt") + 1])
        self.assertEqual(["Agent", "Task"], command[command.index("--disallowedTools") + 1:command.index("--disallowedTools") + 3])
        self.assertNotIn("--permission-mode", command)

    def test_role_session_is_isolated_from_plain_and_changed_roles(self):
        one = self.prepare(self.contract())
        two = self.prepare(self.contract(model_reasoning_effort="high"))
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "test-thread", "FABLE_RELAY_STATE_DIR": str(self.root)}):
            self.assertNotEqual(self.relay._state_path(), self.relay._state_path(one["scope"]))
            self.assertNotEqual(self.relay._state_path(one["scope"]), self.relay._state_path(two["scope"]))

    def test_incompatible_requirements_fail_before_launch(self):
        for changes in ({"model_reasoning_effort": "ultra"}, {"sandbox_mode": "read-only"}, {"agents": {"max_threads": 2}}):
            with self.subTest(changes=changes), self.assertRaises(self.roles.RoleContractError):
                self.prepare(self.contract(**changes))

    def test_native_delegates_keep_shared_contract_and_exact_effort(self):
        root = self.contract("test_coordinator", agents={"enabled": True, "default_subagent_reasoning_effort": "high"})
        child = self.contract("test_specialist", model_reasoning_effort="high")
        role = self.prepare(root, [child])
        definition = role["definitions"]["shared-test_specialist"]
        self.assertEqual("high", definition["effort"])
        self.assertEqual("claude-fable-5-1", definition["model"])
        self.assertEqual(["Agent", "Task"], definition["disallowedTools"])
        with self.assertRaises(self.roles.RoleContractError):
            self.prepare(root)

    def test_individual_role_cannot_accept_delegate_contract(self):
        with self.assertRaises(self.roles.RoleContractError):
            self.prepare(self.contract(), [self.contract("another")])


if __name__ == "__main__":
    unittest.main()
