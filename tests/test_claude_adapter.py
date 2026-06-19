import json
import sys
from jailbird.adapters import get_adapter
from jailbird.types import Task
from jailbird.policy import Policy

A = get_adapter("claude")

def test_name_registered():
    assert A.name == "claude"

def test_build_argv_no_bypass_flag():
    argv = A.build_argv(Task(prompt="hi"), autonomy="auto", config_dir="/tmp/x")
    assert argv[:2] == ["claude", "-p"]
    assert "--dangerously-skip-permissions" not in argv
    assert "--output-format" in argv and "stream-json" in argv
    i = argv.index("--permission-mode")
    assert argv[i + 1] == "dontAsk"

def test_build_argv_autonomy_maps_permission_mode():
    argv = A.build_argv(Task(prompt="hi"), autonomy="plan", config_dir="/tmp/x")
    i = argv.index("--permission-mode")
    assert argv[i + 1] == "plan"

def test_governance_artifact_registers_pretooluse_hook():
    [art] = A.governance_artifacts(Policy(), scope="project")
    assert art.path == ".claude/settings.json"
    data = json.loads(art.content)
    cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd == f"{sys.executable} -m jailbird.govern.hook --vendor claude"

def test_deny_response_exact_contract():
    out = json.loads(A.deny_response("nope"))
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == "nope"

def test_parse_stream_result_cost():
    ev = A.parse_stream(json.dumps({"type": "result", "total_cost_usd": 0.05, "result": "ok"}))
    assert ev.kind == "result" and ev.cost_usd == 0.05

def test_parse_hook_input_extracts_command():
    call = A.parse_hook_input({"tool_name": "Bash", "tool_input": {"command": "git push"}})
    assert call.name == "Bash" and call.command == "git push"

def test_parse_stream_tool_result_error_flags_block():
    line = json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "is_error": True,
         "content": "BLOCKED by jailbird: tool 'Bash' denied"}]}})
    ev = A.parse_stream(line)
    assert ev.kind == "tool_error" and ev.is_error and "BLOCKED by jailbird" in ev.text
