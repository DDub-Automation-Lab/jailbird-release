import pytest
from jailbird.workflow.spec import (
    Stage, FanTask, Workflow, Profile, resolve_vendor, resolve_fan_vendor,
)

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

def test_fan_out_parses_from_yaml(tmp_path):
    p = tmp_path / "wf.yaml"
    p.write_text(
        "name: f\nstages:\n"
        "  - role: implement\n    gate: true\n    fan_out:\n"
        "      - brief: 'part 1 {prev.summary}'\n"
        "      - brief: 'part 2'\n        vendor: codex\n"
        "      - brief: 'part 3'\n        role: qa\n"
    )
    wf = Workflow.from_yaml(str(p))
    st = wf.stages[0]
    assert st.gate is True and len(st.fan_out) == 3
    assert st.fan_out[0].brief == "part 1 {prev.summary}"
    assert st.fan_out[1].vendor == "codex"
    assert st.fan_out[2].role == "qa"

def test_fan_out_branch_requires_brief(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: f\nstages:\n  - role: implement\n    fan_out:\n      - vendor: codex\n")
    with pytest.raises(ValueError):
        Workflow.from_yaml(str(bad))

def test_resolve_fan_vendor_pin_beats_profile():
    st = Stage("implement")
    assert resolve_fan_vendor(FanTask(brief="x", vendor="codex"), st,
                              Profile({"implement": "claude"})) == "codex"

def test_resolve_fan_vendor_uses_branch_role_then_stage_role():
    st = Stage("implement")
    prof = Profile({"implement": "claude", "qa": "antigravity"})
    assert resolve_fan_vendor(FanTask(brief="x", role="qa"), st, prof) == "antigravity"
    assert resolve_fan_vendor(FanTask(brief="x"), st, prof) == "claude"
