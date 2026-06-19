from __future__ import annotations
import json
import os
import sys
from jailbird.adapters.base import VendorAdapter
from jailbird.types import Task, Event, ToolCall, ConfigArtifact
from jailbird.policy import Policy

_PERMISSION = {"plan": "plan", "build": "dontAsk", "auto": "dontAsk"}

class ClaudeAdapter(VendorAdapter):
    name = "claude"
    binary = "claude"

    def build_argv(self, task: Task, *, autonomy: str, config_dir: str) -> list[str]:
        mode = _PERMISSION.get(autonomy, "dontAsk")
        argv = ["claude", "-p", task.prompt,
                "--output-format", "stream-json", "--verbose",
                "--permission-mode", mode]
        settings = os.path.join(config_dir, ".claude", "settings.json")
        if os.path.exists(settings):
            argv += ["--settings", settings]
        return argv

    def governance_artifacts(self, policy: Policy, scope: str) -> list[ConfigArtifact]:
        hook = {"hooks": {"PreToolUse": [
            {"matcher": "*",
             "hooks": [{"type": "command",
                        "command": f"{sys.executable} -m jailbird.govern.hook --vendor claude"}]}]}}
        return [ConfigArtifact(".claude/settings.json", json.dumps(hook, indent=2), "json", True)]

    def parse_stream(self, line: str) -> Event | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return None
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            return Event(kind="init", text=ev.get("model", ""))
        if t == "assistant":
            texts, tool = [], ""
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool = block.get("name", "")
            return Event(kind="tool", tool=tool) if tool else Event(kind="text", text=" ".join(texts))
        if t == "result":
            return Event(kind="result", text=ev.get("result", ""),
                         cost_usd=float(ev.get("total_cost_usd", 0.0)))
        if t == "user":
            for block in ev.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                    c = block.get("content", "")
                    text = c if isinstance(c, str) else " ".join(
                        b.get("text", "") for b in c if isinstance(b, dict))
                    return Event(kind="tool_error", text=text, is_error=True)
            return None
        return None

    def parse_hook_input(self, d: dict) -> ToolCall:
        ti = d.get("tool_input", {}) or {}
        return ToolCall(name=d.get("tool_name", ""), command=ti.get("command", ""),
                        paths=[ti[k] for k in ("file_path", "path") if ti.get(k)], raw_input=ti)

    def deny_response(self, reason: str) -> str:
        return json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason}})
