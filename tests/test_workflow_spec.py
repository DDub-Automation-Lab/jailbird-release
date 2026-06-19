import pytest
from jailbird.workflow.spec import Stage, Workflow, Profile, resolve_vendor

def test_resolve_pin_beats_profile():
    assert resolve_vendor(Stage("design", vendor="codex"), Profile({"design": "claude"})) == "codex"

def test_resolve_uses_profile_when_unpinned():
    assert resolve_vendor(Stage("design"), Profile({"design": "claude"})) == "claude"

def test_resolve_none_when_unset():
    assert resolve_vendor(Stage("design"), Profile.empty()) is None

def test_workflow_from_yaml(tmp_path):
    p = tmp_path / "wf.yaml"
    p.write_text("name: x\nstages:\n  - role: design\n    brief: 'do {task}'\n"
                 "  - role: qa\n    gate: true\n")
    wf = Workflow.from_yaml(str(p))
    assert wf.name == "x" and wf.stages[1].gate is True and wf.stages[0].brief == "do {task}"

def test_workflow_requires_name_and_stages(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("stages: []\n")
    with pytest.raises(ValueError):
        Workflow.from_yaml(str(bad))
