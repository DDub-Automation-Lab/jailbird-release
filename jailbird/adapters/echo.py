from __future__ import annotations
import json
import sys
from jailbird.adapters.base import VendorAdapter
from jailbird.types import Task, Event, ToolCall, ConfigArtifact
from jailbird.policy import Policy

class EchoAdapter(VendorAdapter):
    name = "echo"

    def build_argv(self, task: Task, *, autonomy: str, config_dir: str) -> list[str]:
        argv = [sys.executable, "-m", "jailbird.adapters.echo_agent", "--prompt", task.prompt]
        return argv

    def governance_artifacts(self, policy: Policy, scope: str) -> list[ConfigArtifact]:
        # Echo has no native config; it self-enforces in-process via --policy.
        return []

    def parse_stream(self, line: str) -> Event | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return None
        t = ev.get("type")
        if t == "system":
            return Event(kind="init", text=ev.get("model", "echo"))
        if t == "assistant":
            return Event(kind="text", text=ev.get("text", ""))
        if t == "user" and ev.get("is_error"):
            return Event(kind="tool_error", text=ev.get("text", ""), is_error=True)
        if t == "tool_use":
            return Event(kind="tool", tool=ev.get("name", ""), summary=ev.get("summary", ""))
        if t == "result":
            return Event(kind="result", text=ev.get("result", ""),
                         cost_usd=float(ev.get("total_cost_usd", 0.0)))
        return None

    def parse_hook_input(self, d: dict) -> ToolCall:
        return ToolCall(name=d.get("tool_name", ""), raw_input=d.get("tool_input", {}))

    def deny_response(self, reason: str) -> str:
        return json.dumps({"decision": "deny", "reason": reason})
