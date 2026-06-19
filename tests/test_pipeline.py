# tests/test_pipeline.py
from jailbird.workflow.spec import Workflow, Stage, Profile
from jailbird.workflow.pipeline import run_workflow


def _wf():
    return Workflow(name="t", stages=[
        Stage(role="design", brief="design {task}"),
        Stage(role="build", brief="build {task} TRIGGER_FAIL", gate=True),
        Stage(role="qa", brief="qa {task}"),
    ])


def test_enforcing_gate_halts_before_later_stage(tmp_path):
    res = run_workflow(_wf(), "feature", cwd=str(tmp_path), default_vendor="echo")
    assert res.halted is True
    assert [s.role for s in res.stages] == ["design", "build"]  # qa skipped


def test_no_gate_runs_all_stages(tmp_path):
    res = run_workflow(_wf(), "feature", cwd=str(tmp_path), default_vendor="echo",
                       enforce_gates=False)
    assert res.halted is False
    assert [s.role for s in res.stages] == ["design", "build", "qa"]


def test_prev_summary_interpolates(tmp_path):
    seen = []
    wf = Workflow(name="t", stages=[
        Stage(role="design", brief="design {task}"),
        Stage(role="build", brief="use prev: {prev.summary}"),
    ])
    res = run_workflow(wf, "feature", cwd=str(tmp_path), default_vendor="echo",
                       on_event=lambda e: seen.append(e))
    assert len(res.stages) == 2
    # stage 1's summary ("done") must have been interpolated into stage 2's prompt,
    # which echo echoes back as "echo: use prev: done".
    assert any("use prev: done" in (e.text or "") for e in seen)


def test_blocked_gate_halts(tmp_path):
    wf = Workflow(name="t", stages=[
        Stage(role="build", brief="do {task} TRIGGER_BLOCK", gate=True),
        Stage(role="qa", brief="qa {task}"),
    ])
    res = run_workflow(wf, "x", cwd=str(tmp_path), default_vendor="echo")
    assert res.halted is True
    assert res.stages[0].blocked is True and res.stages[0].returncode == 0
    assert [s.role for s in res.stages] == ["build"]  # qa skipped via the blocked-halt branch


def test_profile_resolves_stage_vendor(tmp_path):
    wf = Workflow(name="t", stages=[Stage(role="design", brief="design {task}")])
    res = run_workflow(wf, "x", cwd=str(tmp_path), profile=Profile({"design": "echo"}))
    assert res.stages[0].vendor == "echo"


def test_absent_vendor_cli_falls_back_to_echo(tmp_path, monkeypatch):
    import jailbird.adapters.base as base
    monkeypatch.setattr(base.shutil, "which", lambda name: None)  # no vendor binary on PATH
    from jailbird.workflow.spec import Profile
    wf = Workflow(name="t", stages=[Stage(role="design", brief="d {task}")])
    res = run_workflow(wf, "x", cwd=str(tmp_path), profile=Profile({"design": "claude"}),
                       default_vendor="echo")
    assert res.stages[0].vendor == "echo"
