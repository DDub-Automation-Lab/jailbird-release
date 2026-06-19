from __future__ import annotations
import json
import os
import shlex
import sys
import tomli_w
from jailbird.adapters.base import VendorAdapter
from jailbird.types import Task, Event, ToolCall, ConfigArtifact
from jailbird.policy import Policy

class CodexAdapter(VendorAdapter):
    name = "codex"
    binary = "codex"
    config_home_env = "CODEX_HOME"

    def harness_env(self, config_dir: str) -> dict[str, str]:
        # Codex reads BOTH config and auth from CODEX_HOME. Only redirect it when a
        # harness config has actually been provisioned here (apply wrote config.toml),
        # so a bare `run` doesn't strip the user's real home of model/auth settings.
        home = os.path.join(config_dir, ".codex")
        if not os.path.exists(os.path.join(home, "config.toml")):
            return {}
        # Preserve login: symlink (not copy) the real auth.json in, so the credential
        # is never duplicated into the throwaway config dir.
        real = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
        src, dst = os.path.join(real, "auth.json"), os.path.join(home, "auth.json")
        if os.path.exists(src) and not os.path.lexists(dst):
            try:
                os.symlink(src, dst)
            except OSError:
                pass
        return {self.config_home_env: home}

    def build_argv(self, task: Task, *, autonomy: str, config_dir: str) -> list[str]:
        # autonomy is folded into approval_policy/sandbox via config; argv stays sandboxed.
        # --json: emit events as JSONL (parse_stream needs it).
        # --skip-git-repo-check: codex exec refuses non-repo dirs otherwise.
        # codex exec is non-interactive (auto-rejects approvals); no -a flag on the subcommand.
        return ["codex", "exec", "--json", "--skip-git-repo-check",
                "--sandbox", "workspace-write", task.prompt]

    def governance_artifacts(self, policy: Policy, scope: str) -> list[ConfigArtifact]:
        config = {
            "approval_policy": "never",
            "sandbox_mode": "workspace-write",
            "hooks": {"PreToolUse": [
                {"matcher": ".*",  # codex matchers are regexes; "*" never compiles
                 "hooks": [{"type": "command",
                            "command": f"{sys.executable} -m jailbird.govern.hook --vendor codex"}]}]},
        }
        cfg = ConfigArtifact(".codex/config.toml", tomli_w.dumps(config), "toml", True)
        rules_lines = []
        for cmd in policy.deny_commands:
            try:
                tokens = shlex.split(cmd)
            except ValueError:
                tokens = [cmd]
            pattern = ", ".join(json.dumps(t) for t in tokens) or json.dumps(cmd)
            rules_lines.append(
                f'prefix_rule(\n    pattern = [{pattern}],\n    decision = "forbidden",\n'
                f'    justification = "Blocked by jailbird policy.",\n)')
        rules = ConfigArtifact(".codex/rules/jailbird.rules", "\n".join(rules_lines) + "\n",
                               "text", False)
        return [cfg, rules]

    def parse_stream(self, line: str) -> Event | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            # Hooks don't fire in `codex exec` (upstream openai/codex#25875), so the
            # live deny path is execpolicy. A `forbidden` rule surfaces as a non-JSON
            # tracing line: `... rejected: Blocked by jailbird policy.`
            low = line.lower()
            if "blocked by jailbird" in low and "reject" in low:
                return Event(kind="tool_error", text="Blocked by jailbird policy.", is_error=True)
            return None
        t = ev.get("type")
        if t == "item.completed":
            item = ev.get("item", {})
            if item.get("type") in ("agent_message", "assistant_message"):
                return Event(kind="text", text=item.get("text", ""))
            if item.get("type") == "command_execution":
                return Event(kind="tool", tool="Bash", summary=item.get("command", ""))
        if t == "turn.completed":
            return Event(kind="result", cost_usd=float(ev.get("usage", {}).get("cost_usd", 0.0)))
        return None

    def parse_hook_input(self, d: dict) -> ToolCall:
        ti = d.get("tool_input", {}) or {}
        return ToolCall(name=d.get("tool_name", ""), command=ti.get("command", ""),
                        paths=[ti[k] for k in ("file_path", "path") if ti.get(k)], raw_input=ti)

    def deny_response(self, reason: str) -> str:
        return json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason}})
