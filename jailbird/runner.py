# jailbird/runner.py
from __future__ import annotations
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from jailbird.adapters import get_adapter
from jailbird.policy import Policy
from jailbird.types import Task, Event
from jailbird.govern.preflight import preflight, PreflightError
from jailbird.router.ledger import Ledger

@dataclass
class RunResult:
    vendor: str
    returncode: int
    cost_usd: float = 0.0
    events: list[Event] = field(default_factory=list)
    stalled: bool = False
    blocked: bool = False

def run(task: Task, vendor: str, *, policy: Policy | None = None, policy_path: str | None = None,
        autonomy: str = "build", config_dir: str | None = None, budget_usd: float | None = None,
        stall_timeout: float = 600.0, ledger: Ledger | None = None, on_event=None) -> RunResult:
    adapter = get_adapter(vendor)
    config_dir = config_dir or task.cwd
    argv = adapter.build_argv(task, autonomy=autonomy, config_dir=config_dir)

    if policy is not None:
        v = preflight(policy, task.prompt, argv)
        if v.decision.value == "deny":
            raise PreflightError(f"preflight refused: {v.reason}")

    env = dict(os.environ)
    env.update(adapter.harness_env(config_dir))
    if policy_path is not None:
        env["JAILBIRD_POLICY"] = os.path.abspath(policy_path)
    elif policy is not None:
        env.setdefault("JAILBIRD_POLICY", os.path.join(config_dir, "jailbird.policy.yaml"))

    # Deterministic block signal: the deny-hook appends here; absence == not blocked.
    fd, sentinel = tempfile.mkstemp(prefix="jailbird-block-")
    os.close(fd)
    os.unlink(sentinel)
    env["JAILBIRD_BLOCK_SENTINEL"] = sentinel

    proc = subprocess.Popen(argv, cwd=task.cwd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, env=env, start_new_session=True)
    last_beat = [time.monotonic()]
    stalled = [False]

    def _kill() -> None:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except (ProcessLookupError, PermissionError):
            pass

    def watchdog() -> None:
        while proc.poll() is None:
            time.sleep(1.0)
            if time.monotonic() - last_beat[0] > stall_timeout:
                stalled[0] = True
                _kill()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    result = RunResult(vendor=vendor, returncode=0)
    assert proc.stdout is not None
    for line in proc.stdout:
        ev = adapter.parse_stream(line)
        if ev is None:
            continue
        last_beat[0] = time.monotonic()
        result.events.append(ev)
        if on_event:
            on_event(ev)
        if ev.is_error and "blocked by jailbird" in ev.text.lower():
            result.blocked = True
        if ev.cost_usd:
            result.cost_usd += ev.cost_usd
            if budget_usd is not None and result.cost_usd > budget_usd:
                _kill()
                break
    proc.wait()
    result.returncode = proc.returncode if proc.returncode is not None else 0
    result.stalled = stalled[0]
    try:
        if os.path.exists(sentinel) and os.path.getsize(sentinel) > 0:
            result.blocked = True
    finally:
        if os.path.exists(sentinel):
            os.unlink(sentinel)
    if ledger is not None:
        ledger.record(vendor, requests=1, est_cost=result.cost_usd)
    return result
