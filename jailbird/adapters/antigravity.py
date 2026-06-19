from __future__ import annotations
import json
import sys
from jailbird.adapters.base import VendorAdapter
from jailbird.types import Task, Event, ToolCall, ConfigArtifact
from jailbird.policy import Policy

# Antigravity CLI (`agy`) — Google's terminal coding agent (Gemini 3.x), the successor
# to the auth-deprecated `gemini` CLI. Headless via `agy --print <prompt>` (plain-text
# output, no stream-json). Governance is a real PreToolUse hook that FIRES and BLOCKS in
# --print mode (proven live), unlike `codex exec`. Deny contract mirrors gemini's
# {"decision":"deny"}. Block detection is via the JAILBIRD_BLOCK_SENTINEL the hook writes
# (agy rewords the denial in its prose stdout, so a string match is unreliable).

class AntigravityAdapter(VendorAdapter):
    name = "antigravity"
    binary = "agy"  # the Antigravity CLI binary is `agy`, not `antigravity`

    def build_argv(self, task: Task, *, autonomy: str, config_dir: str) -> list[str]:
        # --print: run one prompt non-interactively and print. Its value IS the prompt.
        # Never --dangerously-skip-permissions (that disables the governance hook).
        return ["agy", "--print", task.prompt]

    def governance_artifacts(self, policy: Policy, scope: str) -> list[ConfigArtifact]:
        # agy loads <workspace>/.agents/hooks.json. Top level is a map of hook-name ->
        # {Event: [{matcher, hooks:[{command}]}]}. "*" matches all tools; the universal
        # hook evaluates the policy per call (deny_tools by name, deny_commands by command).
        hooks = {"jailbird": {"PreToolUse": [
            {"matcher": "*",
             "hooks": [{"command":
                        f"{sys.executable} -m jailbird.govern.hook --vendor antigravity"}]}]}}
        return [ConfigArtifact(".agents/hooks.json", json.dumps(hooks, indent=2), "json", True)]

    def parse_stream(self, line: str) -> Event | None:
        # agy --print emits plain prose (no JSONL). Surface each line as text; flag the
        # rare line that still names the policy. Authoritative block signal is the sentinel.
        line = line.strip()
        if not line:
            return None
        low = line.lower()
        if "blocked by jailbird" in low or ("jailbird" in low and "denied" in low):
            return Event(kind="tool_error", text=line, is_error=True)
        return Event(kind="text", text=line)

    def parse_hook_input(self, d: dict) -> ToolCall:
        tc = d.get("toolCall", {}) or {}
        args = tc.get("args", {}) or {}
        command = args.get("CommandLine") or args.get("command") or args.get("Command") or ""
        paths = [args[k] for k in ("AbsolutePath", "file_path", "path", "TargetFile") if args.get(k)]
        return ToolCall(name=tc.get("name", ""), command=command, paths=paths, raw_input=args)

    def deny_response(self, reason: str) -> str:
        return json.dumps({"decision": "deny", "reason": reason})
