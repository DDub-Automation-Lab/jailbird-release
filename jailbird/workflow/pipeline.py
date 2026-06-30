# jailbird/workflow/pipeline.py
from __future__ import annotations
import concurrent.futures as cf
import threading
from dataclasses import dataclass, field
from jailbird.adapters import vendor_available
from jailbird.workflow.spec import Workflow, Profile, resolve_vendor, resolve_fan_vendor
from jailbird.policy import Policy
from jailbird.types import Task
from jailbird.runner import run, RunResult
from jailbird.router.router import Router


@dataclass
class _Prev:
    """Carries the last stage's summary for {prev.summary} interpolation."""
    summary: str = ""


@dataclass
class StageResult:
    role: str
    vendor: str
    blocked: bool
    returncode: int
    cost_usd: float
    summary: str


@dataclass
class WorkflowResult:
    name: str
    stages: list[StageResult] = field(default_factory=list)
    halted: bool = False

    @property
    def cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.stages)


def _last_text(res: RunResult) -> str:
    """Return the last non-empty text or result event text from a run."""
    texts = [e.text for e in res.events if e.kind in ("text", "result") and e.text]
    return texts[-1] if texts else ""


def _coerce_available(vendor: str) -> str:
    # spec §8: echo stands in for any vendor whose CLI is absent (availability
    # resolves by the adapter's binary, e.g. antigravity -> `agy`).
    return vendor if vendor_available(vendor) else "echo"


def _pick_vendor(resolved: str | None, role: str, router, candidate_vendors, default_vendor) -> str:
    """Vendor resolution shared by sequential and fan-out units: explicit
    pin/profile (``resolved``) > router (if given candidates) > default."""
    if resolved and resolved != "auto":
        vendor = resolved
    elif router is not None and candidate_vendors:
        vendor = router.choose(candidate_vendors, kind=role)
    else:
        vendor = default_vendor
    return _coerce_available(vendor)


def _run_unit(role, vendor, brief, *, cwd, policy, policy_path, autonomy, ledger, on_event):
    """Run one brief on one vendor and package it as a StageResult."""
    res = run(Task(prompt=brief, cwd=cwd), vendor, policy=policy, policy_path=policy_path,
              autonomy=autonomy, ledger=ledger, on_event=on_event)
    sr = StageResult(role=role, vendor=vendor, blocked=res.blocked,
                     returncode=res.returncode, cost_usd=res.cost_usd,
                     summary=_last_text(res))
    return res, sr


def _run_fan_out(stage, *, task_text, prev, profile, router, candidate_vendors, default_vendor,
                 cwd, policy, policy_path, ledger, on_event, max_parallel):
    """Run a fan-out stage's branches concurrently and return (results, any_fail).

    Branch vendors are assigned *sequentially* first — deterministic, and the request is
    recorded to the ledger at assignment time so the router still spreads later branches.
    Branches then execute on a bounded thread pool; each branch's real cost is recorded when
    it finishes (splitting request/cost recording avoids double-counting and keeps totals
    correct). Results are re-ordered to declaration order so the join and gate are
    deterministic regardless of which branch finishes first.
    """
    # 1. Assign vendors up front (sequential → deterministic spread).
    plans = []
    for i, ft in enumerate(stage.fan_out):
        vendor = _pick_vendor(resolve_fan_vendor(ft, stage, profile),
                              ft.role or stage.role, router, candidate_vendors, default_vendor)
        if ledger is not None:
            ledger.record(vendor, requests=1, est_cost=0.0)
        brief = ft.brief.format(task=task_text, prev=prev)
        plans.append((i, f"{stage.role}[{i}]", vendor, brief))

    # 2. Serialize on_event so concurrently-streamed lines don't interleave mid-line.
    emit = on_event
    if on_event is not None and max_parallel != 1:
        _lock = threading.Lock()
        def emit(e, _cb=on_event, _lk=_lock):  # noqa: E306
            with _lk:
                _cb(e)

    def _exec(plan):
        i, role, vendor, brief = plan
        # ledger=None here: the request was recorded at assignment; record cost on finish.
        res, sr = _run_unit(role, vendor, brief, cwd=cwd, policy=policy, policy_path=policy_path,
                            autonomy=stage.autonomy, ledger=None, on_event=emit)
        if ledger is not None:
            ledger.record(vendor, requests=0, est_cost=res.cost_usd)
        return i, res, sr

    # 3. Run branches. A pool of 1 (or a single branch) runs inline — no threads.
    workers = max(1, min(max_parallel, len(plans)))
    if workers == 1:
        done = [_exec(p) for p in plans]
    else:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            done = list(ex.map(_exec, plans))

    # 4. Re-order to declaration order; gate trips if ANY branch failed or was blocked.
    done.sort(key=lambda d: d[0])
    results = [sr for _, _, sr in done]
    any_fail = any(res.returncode != 0 or res.blocked for _, res, _ in done)
    return results, any_fail


def run_workflow(
    wf: Workflow,
    task_text: str,
    *,
    profile: Profile | None = None,
    router: Router | None = None,
    policy: Policy | None = None,
    policy_path: str | None = None,
    cwd: str = ".",
    default_vendor: str = "echo",
    enforce_gates: bool = True,
    candidate_vendors: list[str] | None = None,
    ledger=None,
    on_event=None,
    max_parallel: int = 8,
) -> WorkflowResult:
    """Run each stage sequentially.

    A stage is either a single unit or a ``fan_out`` group of independent branches
    that run *concurrently* on a bounded pool (``max_parallel``; set 1 for
    sequential). Each branch is routed and governed on its own (it may land on a
    different vendor); results re-order to declaration order and the branch
    summaries are joined for the next stage.

    Vendor resolution order: explicit pin → profile role → router (if provided
    and candidate_vendors given) → default_vendor.  Gate stages halt the
    workflow on non-zero returncode or blocked result when enforce_gates=True;
    a fan-out gate trips if any branch fails or is blocked.
    """
    profile = profile or Profile.empty()
    out = WorkflowResult(name=wf.name)
    prev = _Prev()

    for stage in wf.stages:
        if stage.fan_out:
            # Fan-out: independent branches run concurrently, each routed and governed
            # on its own, then joined. The gate trips if ANY branch fails or is blocked.
            group, any_fail = _run_fan_out(
                stage, task_text=task_text, prev=prev, profile=profile, router=router,
                candidate_vendors=candidate_vendors, default_vendor=default_vendor, cwd=cwd,
                policy=policy, policy_path=policy_path, ledger=ledger, on_event=on_event,
                max_parallel=max_parallel)
            out.stages.extend(group)
            # Join every branch's summary so the next stage sees the whole fan-out.
            prev = _Prev(summary="\n".join(f"[{sr.role}] {sr.summary}" for sr in group))
            if stage.gate and enforce_gates and any_fail:
                out.halted = True
                break
            continue

        vendor = _pick_vendor(resolve_vendor(stage, profile), stage.role, router,
                              candidate_vendors, default_vendor)
        brief = stage.brief.format(task=task_text, prev=prev)
        res, sr = _run_unit(stage.role, vendor, brief, cwd=cwd, policy=policy,
                            policy_path=policy_path, autonomy=stage.autonomy,
                            ledger=ledger, on_event=on_event)
        out.stages.append(sr)
        prev = _Prev(summary=sr.summary)

        if stage.gate and enforce_gates and (res.returncode != 0 or res.blocked):
            out.halted = True
            break

    return out
