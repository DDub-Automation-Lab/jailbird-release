import json
from jailbird.govern.hook import main

def _policy(tmp_path):
    p = tmp_path / "p.yaml"
    p.write_text("deny_commands: ['git push']\ndeny_tools: ['mcp__*__place_*']\n")
    return str(p)

def test_claude_deny_emits_pretooluse(tmp_path):
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin"}})
    code, out = main(["--vendor", "claude", "--policy", _policy(tmp_path)], stdin)
    assert code == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

def test_allow_is_empty(tmp_path):
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    code, out = main(["--vendor", "claude", "--policy", _policy(tmp_path)], stdin)
    assert code == 0 and out == ""

def test_antigravity_deny_emits_decision(tmp_path):
    stdin = json.dumps({"toolCall": {"name": "run_command",
                                     "args": {"CommandLine": "git push origin"}}})
    code, out = main(["--vendor", "antigravity", "--policy", _policy(tmp_path)], stdin)
    assert json.loads(out)["decision"] == "deny"

def test_deny_writes_block_sentinel(tmp_path, monkeypatch):
    sentinel = tmp_path / "block.sentinel"
    monkeypatch.setenv("JAILBIRD_BLOCK_SENTINEL", str(sentinel))
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin"}})
    main(["--vendor", "claude", "--policy", _policy(tmp_path)], stdin)
    assert sentinel.exists() and sentinel.read_text().strip() != ""

def test_allow_does_not_write_sentinel(tmp_path, monkeypatch):
    sentinel = tmp_path / "block.sentinel"
    monkeypatch.setenv("JAILBIRD_BLOCK_SENTINEL", str(sentinel))
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    main(["--vendor", "claude", "--policy", _policy(tmp_path)], stdin)
    assert not sentinel.exists()
