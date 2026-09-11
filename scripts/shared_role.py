"""Adapt an explicitly selected Codex role contract to the Fable runtime.

Contracts are the selected-role JSON emitted by codex:sub-agents/read-roles.py.
They remain caller-owned private files, never a second role registry.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


EFFORTS = {"low", "medium", "high", "xhigh", "max"}
SUPPORTED_CONFIG = {"model", "model_reasoning_effort", "developer_instructions", "agents"}
SUPPORTED_AGENTS = {"enabled", "default_subagent_reasoning_effort"}


class RoleContractError(ValueError):
    """The selected role cannot be faithfully represented by this runtime."""


def load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RoleContractError("Cannot read selected-role JSON contract") from error
    role = payload.get("role") if isinstance(payload, dict) else None
    if not isinstance(role, dict):
        raise RoleContractError("Expected a selected role from read-roles.py --role")
    key, description, config = role.get("key"), role.get("description"), role.get("config")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise RoleContractError("Role key must contain only letters, digits, underscores or hyphens")
    if not isinstance(description, str) or not isinstance(config, dict):
        raise RoleContractError("Role description and full configuration are required")
    unsupported = set(config) - SUPPORTED_CONFIG
    if unsupported:
        raise RoleContractError("Fable cannot preserve role configuration fields: " + ", ".join(sorted(unsupported)))
    for field in ("model", "developer_instructions"):
        if field in config and not isinstance(config[field], str):
            raise RoleContractError(f"Role {field} must be text")
    effort = config.get("model_reasoning_effort")
    if effort is not None and (not isinstance(effort, str) or effort not in EFFORTS):
        raise RoleContractError("Fable cannot run the role's required reasoning effort; no downgrade was made")
    agents = config.get("agents", {})
    if not isinstance(agents, dict) or set(agents) - SUPPORTED_AGENTS:
        raise RoleContractError("Fable cannot preserve the role's agent runtime settings")
    if "enabled" in agents and not isinstance(agents["enabled"], bool):
        raise RoleContractError("Role agents.enabled must be a boolean")
    if "default_subagent_reasoning_effort" in agents and (not isinstance(agents["default_subagent_reasoning_effort"], str) or agents["default_subagent_reasoning_effort"] not in EFFORTS):
        raise RoleContractError("Fable cannot run the required delegate reasoning effort")
    return {"key": key, "description": description, "config": config}


def prepare_role(path: Path | None, delegates: list[Path], *, model: str, default_effort: str) -> dict[str, Any] | None:
    if path is None:
        if delegates:
            raise RoleContractError("Delegate contracts require a selected role contract")
        return None
    role = load_contract(path)
    config = role["config"]
    agents = config.get("agents", {})
    can_delegate = agents.get("enabled", True)
    if delegates and not can_delegate:
        raise RoleContractError("The selected role must work individually; delegate contracts are forbidden")
    effort = config.get("model_reasoning_effort", default_effort)
    definitions = {}
    delegate_roles = []
    for delegate_path in delegates:
        child = load_contract(delegate_path)
        if child["key"] == role["key"] or child["key"] in {item["key"] for item in delegate_roles}:
            raise RoleContractError("Duplicate or recursive delegate role contract")
        child_config = child["config"]
        if child_config.get("agents", {}).get("enabled", True):
            raise RoleContractError("Native delegate roles must work individually; nested delegation is not adapted")
        child_effort = child_config.get("model_reasoning_effort", agents.get("default_subagent_reasoning_effort", effort))
        native_name = "shared-" + child["key"]
        definitions[native_name] = {
            "description": child["description"] or child["key"],
            "prompt": child_config.get("developer_instructions", "") + "\nWork individually. Do not spawn, contact, or delegate to other agents or threads.",
            "model": model,
            "effort": child_effort,
            "disallowedTools": ["Agent", "Task"],
        }
        delegate_roles.append(child)
    if can_delegate and agents.get("default_subagent_reasoning_effort") and not definitions:
        raise RoleContractError("This role requires configured delegates; supply their read-roles.py output with --delegate-role-contract")
    instructions = (
        f"\n\nAssigned role: {role['key']}\n{role['description']}\n"
        + config.get("developer_instructions", "")
        + "\nThe user selected Fable as the participant. The role assigns responsibilities, not a replacement model."
    )
    if not can_delegate:
        instructions += "\nWork individually. Do not spawn, contact, or delegate to other agents or threads, including through shell commands."
    elif definitions:
        instructions += (
            "\nDelegate only to the following native agents when permitted by the role instructions: "
            + ", ".join(definitions)
            + ". These are the supplied shared role contracts with their configured reasoning effort. Do not substitute generic agents or start nested Claude CLI sessions."
        )
    digest = hashlib.sha256(json.dumps({"role": role, "delegates": delegate_roles}, sort_keys=True).encode()).hexdigest()
    return {
        "key": role["key"], "effort": effort, "instructions": instructions,
        "can_delegate": can_delegate, "definitions": definitions, "scope": digest,
    }
