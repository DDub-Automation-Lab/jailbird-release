# tests/test_runner.py
import pytest
from jailbird.runner import run
from jailbird.types import Task
from jailbird.policy import Policy
from jailbird.govern.preflight import PreflightError
from jailbird.router.ledger import Ledger

def test_echo_happy_path_records_ledger(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    res = run(Task(prompt="hello", cwd=str(tmp_path)), "echo", ledger=led)
    assert res.returncode == 0
    assert abs(res.cost_usd - 0.01) < 1e-9
    assert any(e.kind == "result" for e in res.events)
    assert led.totals()["echo"].requests == 1

def test_preflight_refuses_denied_prompt(tmp_path):
    pol = Policy(deny_commands=["git push"])
    with pytest.raises(PreflightError):
        run(Task(prompt="please git push to origin", cwd=str(tmp_path)), "echo", policy=pol)

def test_on_event_callback_fires(tmp_path):
    seen = []
    run(Task(prompt="hi", cwd=str(tmp_path)), "echo", on_event=seen.append)
    assert any(e.kind == "result" for e in seen)


def test_policy_path_threaded_to_child_env(tmp_path, monkeypatch):
    import os as _os
    import jailbird.runner as rn
    captured = {}
    real_popen = rn.subprocess.Popen
    def fake_popen(argv, **kw):
        captured["env"] = kw.get("env")
        return real_popen(argv, **kw)
    monkeypatch.setattr(rn.subprocess, "Popen", fake_popen)
    polfile = tmp_path / "custom.policy.yaml"
    polfile.write_text("deny_commands: ['zzz']\n")
    run(Task(prompt="hi", cwd=str(tmp_path)), "echo",
        policy=Policy(deny_commands=["zzz"]), policy_path=str(polfile))
    assert captured["env"]["JAILBIRD_POLICY"] == _os.path.abspath(str(polfile))


def test_blocked_set_from_echo_midrun_block(tmp_path):
    # Offline analogue of the codex live proof: the runner flips blocked when an
    # agent reports a mid-run policy denial. Echo emits "BLOCKED by jailbird policy
    # (simulated mid-run block)" on TRIGGER_BLOCK; detection is case-insensitive so
    # it also catches codex's "... rejected: Blocked by jailbird policy.".
    res = run(Task(prompt="do the thing TRIGGER_BLOCK", cwd=str(tmp_path)), "echo",
              autonomy="auto")
    assert res.blocked is True


def test_blocked_from_sentinel_file(tmp_path, monkeypatch):
    # The hook writes to JAILBIRD_BLOCK_SENTINEL on deny; the runner must detect it
    # (deterministic, paraphrase-proof — needed for agy whose stdout is reworded prose).
    import jailbird.runner as rn
    real_popen = rn.subprocess.Popen
    def fake_popen(argv, **kw):
        s = (kw.get("env") or {}).get("JAILBIRD_BLOCK_SENTINEL")
        if s:
            with open(s, "a") as f:  # simulate the vendor's hook denying a tool
                f.write("tool 'run_command' denied\n")
        return real_popen(["echo", "{}"], **kw)
    monkeypatch.setattr(rn.subprocess, "Popen", fake_popen)
    res = run(Task(prompt="hi", cwd=str(tmp_path)), "echo")
    assert res.blocked is True


def test_codex_home_threaded_to_child_env(tmp_path, monkeypatch):
    # When a codex config home is provisioned, runner must point CODEX_HOME at it
    # (so the vendor loads the harness-owned execpolicy/config), without running codex.
    import jailbird.runner as rn
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("approval_policy = \"never\"\n")
    captured = {}
    real_popen = rn.subprocess.Popen
    def fake_popen(argv, **kw):
        captured["env"] = kw.get("env")
        return real_popen(["echo", "{}"], **kw)  # benign stand-in for the codex CLI
    monkeypatch.setattr(rn.subprocess, "Popen", fake_popen)
    run(Task(prompt="hi", cwd=str(tmp_path)), "codex")
    assert captured["env"]["CODEX_HOME"] == str(tmp_path / ".codex")


def test_blocked_set_from_execpolicy_rejection(tmp_path, monkeypatch):
    # A codex execpolicy denial (non-JSON tracing line) must flip RunResult.blocked.
    import jailbird.runner as rn
    reject = ('2026-06-19T03:00:25Z ERROR codex_core::tools::router: error=exec_command failed '
              'for `/bin/zsh -lc \'echo X\'`: Rejected("`...` rejected: Blocked by jailbird policy.")\n')

    class FakeProc:
        def __init__(self):
            self.stdout = iter([reject])
            self.returncode = 0
            self.pid = 0
        def poll(self):
            return 0
        def wait(self):
            return 0

    monkeypatch.setattr(rn.subprocess, "Popen", lambda *a, **k: FakeProc())
    res = run(Task(prompt="hi", cwd=str(tmp_path)), "codex")
    assert res.blocked is True
