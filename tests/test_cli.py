# tests/test_cli.py
from jailbird.cli import main


def test_apply_dry_run_writes_nothing(tmp_path, capsys):
    pol = tmp_path / "p.yaml"
    pol.write_text("deny_commands: ['git push']\n")
    code = main(["apply", "--policy", str(pol), "--vendors", "claude",
                 "--base", str(tmp_path), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0 and "DRYRUN" in out and ".claude/settings.json" in out
    assert not (tmp_path / ".claude").exists()


def test_run_echo_reports_rc(tmp_path, capsys):
    code = main(["run", "--vendor", "echo", "--prompt", "hello",
                 "--cwd", str(tmp_path), "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert code == 0 and "rc=0" in out


def test_route_explain(tmp_path, capsys):
    code = main(["route", "--vendors", "echo", "claude",
                 "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert code == 0 and "chosen:" in out


def test_run_denied_prompt_returns_nonzero_cleanly(tmp_path, capsys):
    pol = tmp_path / "p.yaml"
    pol.write_text("deny_commands: ['git push']\n")
    code = main(["run", "--vendor", "echo", "--policy", str(pol),
                 "--prompt", "now git push origin", "--cwd", str(tmp_path),
                 "--ledger", str(tmp_path / "l.jsonl")])
    err = capsys.readouterr().err
    assert code != 0 and "REFUSED" in err


def test_run_workflow_gate(tmp_path, capsys):
    wf = tmp_path / "wf.yaml"
    wf.write_text("name: t\nstages:\n  - role: design\n    brief: 'design {task}'\n"
                  "  - role: build\n    brief: 'build {task} TRIGGER_FAIL'\n    gate: true\n"
                  "  - role: qa\n    brief: 'qa {task}'\n")
    led = str(tmp_path / "l.jsonl")
    code = main(["run", "--workflow", str(wf), "--task", "x", "--vendor", "echo",
                 "--cwd", str(tmp_path), "--ledger", led])
    assert code == 1 and "halted=True" in capsys.readouterr().out
    code2 = main(["run", "--workflow", str(wf), "--task", "x", "--vendor", "echo",
                  "--no-gate", "--cwd", str(tmp_path), "--ledger", led])
    assert code2 == 0 and "halted=False" in capsys.readouterr().out
