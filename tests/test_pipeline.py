# tests/test_pipeline.py
import pytest
from jailbird.workflow.spec import Workflow, Stage, FanTask, Profile
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


def test_fan_out_runs_every_branch(tmp_path):
    wf = Workflow(name="t", stages=[
        Stage(role="design", brief="design {task}"),
        Stage(role="impl", fan_out=[
            FanTask(brief="part 1 {task}"),
            FanTask(brief="part 2 {task}"),
            FanTask(brief="part 3 {task}"),
        ]),
    ])
    res = run_workflow(wf, "feature", cwd=str(tmp_path), default_vendor="echo")
    assert res.halted is False
    assert [s.role for s in res.stages] == ["design", "impl[0]", "impl[1]", "impl[2]"]
    # every branch ran on echo and billed into the total
    assert res.cost_usd == sum(s.cost_usd for s in res.stages)


def test_fan_out_gate_halts_when_any_branch_fails(tmp_path):
    wf = Workflow(name="t", stages=[
        Stage(role="impl", gate=True, fan_out=[
            FanTask(brief="ok part {task}"),
            FanTask(brief="bad part {task} TRIGGER_FAIL"),
            FanTask(brief="another part {task}"),
        ]),
        Stage(role="qa", brief="qa {task}"),
    ])
    res = run_workflow(wf, "feature", cwd=str(tmp_path), default_vendor="echo")
    assert res.halted is True
    # all three branches still ran (fan-out joins before gating); qa is skipped
    assert [s.role for s in res.stages] == ["impl[0]", "impl[1]", "impl[2]"]
    assert res.stages[1].returncode != 0


def test_fan_out_joined_summary_feeds_next_stage(tmp_path):
    seen = []
    wf = Workflow(name="t", stages=[
        Stage(role="impl", fan_out=[FanTask(brief="a"), FanTask(brief="b")]),
        Stage(role="qa", brief="review: {prev.summary}"),
    ])
    run_workflow(wf, "x", cwd=str(tmp_path), default_vendor="echo",
                 on_event=lambda e: seen.append(e))
    # both branch summaries ("done") are joined and interpolated into qa's prompt
    assert any("[impl[0]] done" in (e.text or "") and "[impl[1]] done" in (e.text or "")
               for e in seen)


def test_fan_out_branch_pins_vendor(tmp_path):
    wf = Workflow(name="t", stages=[
        Stage(role="impl", fan_out=[
            FanTask(brief="a", vendor="echo"),
            FanTask(brief="b"),
        ]),
    ])
    res = run_workflow(wf, "x", cwd=str(tmp_path), profile=Profile({"impl": "echo"}))
    assert [s.vendor for s in res.stages] == ["echo", "echo"]


def test_fan_out_parallel_preserves_declaration_order(tmp_path):
    # Six branches on the default pool must re-order to impl[0..5] regardless of
    # which subprocess finishes first.
    wf = Workflow(name="t", stages=[
        Stage(role="impl", fan_out=[FanTask(brief=f"part {n}") for n in range(6)]),
    ])
    res = run_workflow(wf, "x", cwd=str(tmp_path), default_vendor="echo")
    assert [s.role for s in res.stages] == [f"impl[{i}]" for i in range(6)]


def test_fan_out_max_parallel_one_runs_sequentially(tmp_path):
    wf = Workflow(name="t", stages=[
        Stage(role="impl", fan_out=[FanTask(brief="a"), FanTask(brief="b"), FanTask(brief="c")]),
    ])
    res = run_workflow(wf, "x", cwd=str(tmp_path), default_vendor="echo", max_parallel=1)
    assert [s.role for s in res.stages] == ["impl[0]", "impl[1]", "impl[2]"]
    assert res.halted is False


def test_fan_out_ledger_records_one_request_and_cost_per_branch(tmp_path):
    from jailbird.router.ledger import Ledger
    led = Ledger(str(tmp_path / "l.jsonl"))
    wf = Workflow(name="t", stages=[
        Stage(role="impl", fan_out=[FanTask(brief="a"), FanTask(brief="b"), FanTask(brief="c")]),
    ])
    run_workflow(wf, "x", cwd=str(tmp_path), default_vendor="echo", ledger=led)
    totals = led.totals()
    # split request/cost recording must net exactly one request + the real cost per branch
    assert totals["echo"].requests == 3
    assert totals["echo"].est_cost == pytest.approx(0.03)


def test_absent_vendor_cli_falls_back_to_echo(tmp_path, monkeypatch):
    import jailbird.adapters.base as base
    monkeypatch.setattr(base.shutil, "which", lambda name: None)  # no vendor binary on PATH
    from jailbird.workflow.spec import Profile
    wf = Workflow(name="t", stages=[Stage(role="design", brief="d {task}")])
    res = run_workflow(wf, "x", cwd=str(tmp_path), profile=Profile({"design": "claude"}),
                       default_vendor="echo")
    assert res.stages[0].vendor == "echo"
