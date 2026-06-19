import json
import os
import sys
import tomllib
from jailbird.adapters import get_adapter
from jailbird.types import Task
from jailbird.policy import Policy

A = get_adapter("codex")

def test_build_argv_keeps_sandbox_on_no_yolo():
    argv = A.build_argv(Task(prompt="hi"), autonomy="auto", config_dir="/tmp/x")
    assert argv[:2] == ["codex", "exec"]
    assert "--sandbox" in argv and "workspace-write" in argv
    assert "--json" in argv and "--skip-git-repo-check" in argv
    assert argv[-1] == "hi"  # prompt stays the trailing positional
    for bad in ("--yolo", "--dangerously-bypass-approvals-and-sandbox", "danger-full-access", "-a"):
        assert bad not in argv

def test_governance_emits_config_and_rules():
    arts = {a.path: a for a in A.governance_artifacts(
        Policy(deny_commands=["git push", "rm -rf"]), scope="project")}
    cfg = tomllib.loads(arts[".codex/config.toml"].content)
    assert cfg["approval_policy"] == "never" and cfg["sandbox_mode"] == "workspace-write"
    assert cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == \
        f"{sys.executable} -m jailbird.govern.hook --vendor codex"
    rules = arts[".codex/rules/jailbird.rules"].content
    assert 'decision = "forbidden"' in rules and '"push"' in rules

def test_deny_response_matches_claude_contract():
    out = json.loads(A.deny_response("x"))
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecisionReason"] == "x"


def test_governance_handles_malformed_command():
    arts = {a.path: a for a in A.governance_artifacts(
        Policy(deny_commands=["git commit -m 'wip"]), scope="project")}
    rules = arts[".codex/rules/jailbird.rules"].content
    assert 'decision = "forbidden"' in rules  # did not crash; a rule was rendered

def test_parse_stream_text_and_result():
    txt = A.parse_stream(json.dumps({"type": "item.completed",
                                     "item": {"type": "agent_message", "text": "hello"}}))
    assert txt.kind == "text" and txt.text == "hello"
    res = A.parse_stream(json.dumps({"type": "turn.completed", "usage": {"cost_usd": 0.03}}))
    assert res.kind == "result" and res.cost_usd == 0.03


def test_hook_matcher_is_regex_not_glob():
    # Codex matchers are regexes; a bare "*" is an invalid regex that never
    # matches, silently disabling the hook (".*" matches all tools).
    arts = {a.path: a for a in A.governance_artifacts(Policy(), scope="project")}
    cfg = tomllib.loads(arts[".codex/config.toml"].content)
    assert cfg["hooks"]["PreToolUse"][0]["matcher"] == ".*"


def test_parse_stream_detects_execpolicy_rejection():
    # codex execpolicy denial surfaces as a non-JSON tracing line, e.g.
    #   ...router: error=exec_command failed for `...`: Rejected("`...` rejected: Blocked by jailbird policy.")
    line = ('2026-06-19T03:00:25Z ERROR codex_core::tools::router: error=exec_command failed '
            'for `/bin/zsh -lc \'echo X\'`: CreateProcess { message: '
            '"Rejected(\\"`/bin/zsh -lc \'echo X\'` rejected: Blocked by jailbird policy.\\")" }')
    ev = A.parse_stream(line)
    assert ev is not None and ev.is_error
    assert "blocked by jailbird" in ev.text.lower()


def test_harness_env_redirects_codex_home_when_config_present(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("approval_policy = \"never\"\n")
    env = A.harness_env(str(tmp_path))
    assert env["CODEX_HOME"] == str(tmp_path / ".codex")


def test_harness_env_noop_without_provisioned_config(tmp_path):
    # No .codex/config.toml provisioned here -> don't hijack the user's real CODEX_HOME.
    assert A.harness_env(str(tmp_path)) == {}


def test_harness_env_symlinks_auth(tmp_path, monkeypatch):
    real_home = tmp_path / "real_codex"
    real_home.mkdir()
    (real_home / "auth.json").write_text("{\"tokens\": \"x\"}")
    monkeypatch.setenv("CODEX_HOME", str(real_home))
    cfg_dir = tmp_path / "work"
    (cfg_dir / ".codex").mkdir(parents=True)
    (cfg_dir / ".codex" / "config.toml").write_text("approval_policy = \"never\"\n")
    A.harness_env(str(cfg_dir))
    linked = cfg_dir / ".codex" / "auth.json"
    assert linked.is_symlink()
    assert os.path.realpath(linked) == os.path.realpath(real_home / "auth.json")
