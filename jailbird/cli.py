# jailbird/cli.py
from __future__ import annotations
import argparse
import sys
from jailbird.policy import Policy
from jailbird.govern.provision import apply, check
from jailbird.govern.preflight import PreflightError
from jailbird.runner import run
from jailbird.router.ledger import Ledger
from jailbird.router.quota import BudgetCapQuota
from jailbird.router.router import Router
from jailbird.workflow.spec import Workflow, Profile
from jailbird.workflow.pipeline import run_workflow
from jailbird.types import Task, Event

DEFAULT_LEDGER = ".jailbird/ledger.jsonl"


def _print_event(e: Event) -> None:
    if e.kind == "text" and e.text:
        print(e.text)
    elif e.kind == "tool":
        print(f"-> {e.tool} {e.summary}".rstrip())
    elif e.kind == "tool_error":
        print(f"x {e.text}")


def cmd_apply(args: argparse.Namespace) -> int:
    pol = Policy.from_yaml(args.policy)
    if args.check:
        drift = check(pol, args.vendors, scope=args.scope, base=args.base)
        for d in drift:
            print(f"DRIFT {d}")
        return 1 if drift else 0
    paths = apply(pol, args.vendors, scope=args.scope, base=args.base,
                  dry_run=args.dry_run, remove=args.remove)
    verb = "DRYRUN" if args.dry_run else ("REMOVE" if args.remove else "WROTE")
    for p in paths:
        print(f"{verb} {p}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    pol = Policy.from_yaml(args.policy) if args.policy else None
    led = Ledger(args.ledger)
    try:
        if args.workflow:
            wf = Workflow.from_yaml(args.workflow)
            profile = Profile.from_yaml(args.profile) if args.profile else Profile.empty()
            router = Router(led, BudgetCapQuota({}, led), args.strategy)
            result = run_workflow(
                wf, args.task or args.prompt or "",
                profile=profile, router=router, policy=pol, policy_path=args.policy, cwd=args.cwd,
                default_vendor=args.vendor or "echo", enforce_gates=not args.no_gate,
                candidate_vendors=args.candidates or ["echo"], ledger=led,
                on_event=_print_event, max_parallel=args.max_parallel,
            )
            for s in result.stages:
                print(f"[{s.role}] vendor={s.vendor} rc={s.returncode} "
                      f"blocked={s.blocked} ${s.cost_usd:.4f}")
            print(f"halted={result.halted} total=${result.cost_usd:.4f}")
            return 1 if result.halted else 0
        res = run(
            Task(prompt=args.prompt or "", cwd=args.cwd),
            args.vendor or "echo",
            policy=pol, policy_path=args.policy, autonomy=args.autonomy, budget_usd=args.budget,
            ledger=led, on_event=_print_event,
        )
        print(f"rc={res.returncode} blocked={res.blocked} ${res.cost_usd:.4f}")
        return res.returncode
    except PreflightError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2


def cmd_route(args: argparse.Namespace) -> int:
    led = Ledger(args.ledger)
    router = Router(led, BudgetCapQuota({}, led), args.strategy)
    choice = router.choose(args.vendors, kind=args.kind, require_cli=args.require_cli)
    totals = led.totals()
    print(f"chosen: {choice}  (strategy={args.strategy}, kind={args.kind})")
    for v in args.vendors:
        u = totals.get(v)
        print(f"  {v}: requests={u.requests if u else 0} est_cost={u.est_cost if u else 0.0}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jailbird")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("apply", help="provision governance config for vendors")
    a.add_argument("--policy", default="jailbird.policy.yaml")
    a.add_argument("--vendors", nargs="+", default=["claude", "codex", "antigravity"])
    a.add_argument("--scope", choices=["project", "user", "system"], default="project")
    a.add_argument("--base", default=".")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--check", action="store_true")
    a.add_argument("--remove", action="store_true")
    a.set_defaults(func=cmd_apply)

    r = sub.add_parser("run", help="run a governed task or workflow")
    r.add_argument("--vendor", default=None)
    r.add_argument("--prompt", default=None)
    r.add_argument("--task", default=None)
    r.add_argument("--workflow", default=None)
    r.add_argument("--profile", default=None)
    r.add_argument("--policy", default=None)
    r.add_argument("--cwd", default=".")
    r.add_argument("--autonomy", choices=["plan", "build", "auto"], default="build")
    r.add_argument("--budget", type=float, default=None)
    r.add_argument("--strategy", default="weighted_quota")
    r.add_argument("--candidates", nargs="+", default=None)
    r.add_argument("--no-gate", action="store_true")
    r.add_argument("--max-parallel", type=int, default=8,
                   help="max fan-out branches to run concurrently (1 = sequential)")
    r.add_argument("--ledger", default=DEFAULT_LEDGER)
    r.set_defaults(func=cmd_run)

    ro = sub.add_parser("route", help="explain which vendor the router would pick")
    ro.add_argument("--vendors", nargs="+", required=True)
    ro.add_argument("--strategy", default="weighted_quota")
    ro.add_argument("--kind", default=None)
    ro.add_argument("--require-cli", action=argparse.BooleanOptionalAction, default=True)
    ro.add_argument("--ledger", default=DEFAULT_LEDGER)
    ro.set_defaults(func=cmd_route)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
