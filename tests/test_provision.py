import json
import sys
from jailbird.govern.provision import apply, check
from jailbird.policy import Policy

POL = Policy(deny_commands=["git push"], deny_tools=["mcp__*__place_*"])

def test_apply_writes_and_is_idempotent(tmp_path):
    w1 = apply(POL, ["claude", "antigravity"], scope="project", base=str(tmp_path))
    assert any(".claude/settings.json" in p for p in w1)
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == \
        f"{sys.executable} -m jailbird.govern.hook --vendor claude"
    # second apply produces identical content (idempotent)
    before = (tmp_path / ".claude/settings.json").read_text()
    apply(POL, ["claude", "antigravity"], scope="project", base=str(tmp_path))
    assert (tmp_path / ".claude/settings.json").read_text() == before

def test_apply_merges_preserves_existing_keys(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(json.dumps({"model": "opus", "hooks": {"PostToolUse": []}}))
    apply(POL, ["claude"], scope="project", base=str(tmp_path))
    merged = json.loads((d / "settings.json").read_text())
    assert merged["model"] == "opus"  # preserved
    assert "PreToolUse" in merged["hooks"] and "PostToolUse" in merged["hooks"]

def test_dry_run_writes_nothing(tmp_path):
    apply(POL, ["claude"], scope="project", base=str(tmp_path), dry_run=True)
    assert not (tmp_path / ".claude").exists()

def test_check_reports_missing(tmp_path):
    missing = check(POL, ["claude"], scope="project", base=str(tmp_path))
    assert any(".claude/settings.json" in m for m in missing)

def test_apply_preserves_existing_pretooluse_hook(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    existing = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-own-hook"}]}]}}
    (d / "settings.json").write_text(json.dumps(existing))
    apply(POL, ["claude"], scope="project", base=str(tmp_path))
    merged = json.loads((d / "settings.json").read_text())
    cmds = [h["command"] for entry in merged["hooks"]["PreToolUse"] for h in entry["hooks"]]
    assert "my-own-hook" in cmds                          # user hook preserved
    assert any("--vendor claude" in c for c in cmds)      # jailbird hook added
    before = (d / "settings.json").read_text()
    apply(POL, ["claude"], scope="project", base=str(tmp_path))
    assert (d / "settings.json").read_text() == before    # idempotent: no duplication

def test_apply_remove_deletes(tmp_path):
    apply(POL, ["claude"], scope="project", base=str(tmp_path))
    assert (tmp_path / ".claude/settings.json").exists()
    apply(POL, ["claude"], scope="project", base=str(tmp_path), remove=True)
    assert not (tmp_path / ".claude/settings.json").exists()

def test_check_reports_no_drift_after_apply(tmp_path):
    apply(POL, ["claude"], scope="project", base=str(tmp_path))
    assert check(POL, ["claude"], scope="project", base=str(tmp_path)) == []
