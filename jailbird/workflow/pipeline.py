# jailbird/workflow/pipeline.py
from __future__ import annotations
from dataclasses import dataclass, field
from jailbird.adapters import vendor_available
from jailbird.workflow.spec import Workflow, Profile, resolve_vendor
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

    Vendor resolution order: explicit pin → profile role → router (if provided
    and candidate_vendors given) → default_vendor.  Gate stages halt the
    workflow on non-zero returncode or blocked result when enforce_gates=True.
    """
    profile = profile or Profile.empty()
    out = WorkflowResult(name=wf.name)
    prev = _Prev()

    for stage in wf.stages:
        # Resolve vendor: pin > profile > router > default
        resolved = resolve_vendor(stage, profile)
        if resolved and resolved != "auto":
            vendor = resolved
        elif router is not None and candidate_vendors:
            vendor = router.choose(candidate_vendors, kind=stage.role)
        else:
            vendor = default_vendor

        if not vendor_available(vendor):
            vendor = "echo"  # spec §8: echo stands in for any vendor whose CLI is absent
            # (availability resolves by the adapter's binary, e.g. antigravity -> `agy`)

        brief = stage.brief.format(task=task_text, prev=prev)
        res = run(
            Task(prompt=brief, cwd=cwd),
            vendor,
            policy=policy,
            policy_path=policy_path,
            autonomy=stage.autonomy,
            ledger=ledger,
            on_event=on_event,
        )

        summary = _last_text(res)
        out.stages.append(
            StageResult(
                role=stage.role,
                vendor=vendor,
                blocked=res.blocked,
                returncode=res.returncode,
                cost_usd=res.cost_usd,
                summary=summary,
            )
        )
        prev = _Prev(summary=summary)

        if stage.gate and enforce_gates and (res.returncode != 0 or res.blocked):
            out.halted = True
            break

    return out
