# tests/test_examples.py
import glob
import pytest
from jailbird.workflow.spec import Workflow
from jailbird.cli import main
from jailbird.govern.preflight import PreflightError


def test_all_presets_and_example_workflows_parse():
    files = (glob.glob("workflows/*.yaml")
             + glob.glob("examples/**/*.workflow.yaml", recursive=True))
    assert files, "no workflow yaml files found — did presets/examples get created?"
    for f in files:
        wf = Workflow.from_yaml(f)
        assert wf.name and wf.stages


def test_example_01_hello_echo_runs(tmp_path):
    assert main(["run", "--vendor", "echo", "--prompt", "hello",
                 "--cwd", str(tmp_path), "--ledger", str(tmp_path / "l.jsonl")]) == 0


def test_example_03_relay_runs_on_echo(tmp_path, monkeypatch, capsys):
    import jailbird.adapters.base as base
    monkeypatch.setattr(base.shutil, "which", lambda name: None)  # no vendor binary on PATH
    code = main(["run", "--workflow", "examples/03-multi-model-relay/design-build-qa.workflow.yaml",
                 "--profile", "examples/03-multi-model-relay/jailbird.profile.yaml",
                 "--task", "add a healthcheck endpoint", "--vendor", "echo",
                 "--cwd", str(tmp_path), "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("vendor=echo") == 3


def test_example_02_governed_deny_refuses(tmp_path):
    from jailbird.policy import Policy
    from jailbird.runner import run
    from jailbird.types import Task
    pol = Policy.from_yaml("examples/02-governed-deny/no-push.policy.yaml")
    with pytest.raises(PreflightError):
        run(Task(prompt="now git push origin main", cwd=str(tmp_path)), "echo", policy=pol)
