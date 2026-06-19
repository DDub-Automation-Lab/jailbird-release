from jailbird.govern.compile import compile_policy
from jailbird.policy import Policy

def test_compile_three_vendors():
    out = compile_policy(Policy(deny_commands=["git push"]),
                         ["claude", "codex", "antigravity"], "project")
    assert set(out) == {"claude", "codex", "antigravity"}
    assert any(a.path == ".claude/settings.json" for a in out["claude"])
    assert any(a.path == ".codex/rules/jailbird.rules" for a in out["codex"])
    assert any(a.path == ".agents/hooks.json" for a in out["antigravity"])

def test_echo_compiles_empty():
    out = compile_policy(Policy(), ["echo"], "project")
    assert out["echo"] == []
