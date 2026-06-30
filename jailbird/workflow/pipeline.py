# jailbird/workflow/pipeline.py
from __future__ import annotations
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
) -> WorkflowResult:
    """Run each stage sequentially.

    A stage is either a single unit or a ``fan_out`` group of independent
    branches; each branch is routed and governed on its own (it may land on a
    different vendor) and the branch summaries are joined for the next stage.

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
            # Fan-out: independent branches, each routed and governed on its own,
            # then joined. The gate trips if ANY branch fails or is blocked.
            group: list[StageResult] = []
            any_fail = False
            for i, ft in enumerate(stage.fan_out):
                vendor = _pick_vendor(resolve_fan_vendor(ft, stage, profile),
                                      ft.role or stage.role, router, candidate_vendors,
                                      default_vendor)
                brief = ft.brief.format(task=task_text, prev=prev)
                res, sr = _run_unit(f"{stage.role}[{i}]", vendor, brief, cwd=cwd,
                                    policy=policy, policy_path=policy_path,
                                    autonomy=stage.autonomy, ledger=ledger, on_event=on_event)
                group.append(sr)
                any_fail = any_fail or res.returncode != 0 or res.blocked
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
