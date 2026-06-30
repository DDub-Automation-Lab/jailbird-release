# Fan-out stages: governed, cross-vendor branches

A workflow stage normally runs as one unit. A **fan-out** stage splits into several
independent *branches* that each route and govern on their own vendor, then re-converge
into a single joined summary that feeds the next stage. Design once, split the work across
vendors, gate the join.

This is jailbird's take on deep-agents' *dynamic subagents* — but kept deterministic and
auditable: branches are declared in the workflow spec (not spawned ad-hoc by a model), and
every branch inherits the run's deny-policy and writes to the same usage ledger. The thing a
single-process subagent harness can't give you — *governed, cross-vendor* fan-out where each
branch can land on a different vendor under one policy — is exactly what this adds.

> **Status:** branches execute **concurrently** on a bounded thread pool
> (`--max-parallel`, default 8; set `1` for sequential). Vendor assignment is sequential and
> deterministic, and results re-order to declaration order at the join, so a parallel run is
> reproducible. See [Execution model](#execution-model) below.

## TL;DR

```yaml
# workflows/fan-out.yaml
name: fan-out
stages:
  - role: design
    brief: "Split this task into independent, parallelizable parts: {task}"
  - role: implement
    gate: true                 # halts if ANY branch fails or is blocked
    fan_out:
      - { brief: "Implement part 1 of the design. Context: {prev.summary}" }
      - { brief: "Implement part 2 of the design. Context: {prev.summary}" }
      - { brief: "Implement part 3 of the design. Context: {prev.summary}" }
  - role: qa
    gate: true
    brief: "Review the combined diff for correctness & integration risks. Context: {prev.summary}"
```

```bash
jailbird run --workflow workflows/fan-out.yaml \
  --task "add healthz, readyz, and metrics endpoints" \
  --candidates claude codex antigravity --strategy weighted_quota
```

## When to use it

| Use a **sequential** stage when… | Use a **fan-out** stage when… |
|---|---|
| The next step depends on this step's output | The sub-tasks are independent of each other |
| You want a single owner for a phase | You want to spread work across vendors / subscriptions |
| Example: design → implement → qa | Example: implement three unrelated endpoints at once |

Fan-out is for the *parallelizable middle* of a pipeline. A typical shape is **converge →
diverge → converge**: one design stage produces a plan, a fan-out stage implements its
independent parts, and one QA stage reviews the joined result.

## Spec reference

A stage is a fan-out stage as soon as it has a non-empty `fan_out:` list. The stage's own
`brief` is optional in that case (the branches carry the briefs).

### Stage fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `role` | string | *required* | Phase label; also the default vendor-resolution key and the prefix of each branch's result role (`role[i]`) |
| `brief` | string | `""` | Ignored when `fan_out` is set; used for a normal sequential stage |
| `vendor` | string | — | Pins a sequential stage's vendor (not used by fan-out branches) |
| `autonomy` | `plan`\|`build`\|`auto` | `build` | Passed to every branch in the stage |
| `gate` | bool | `false` | If true, the stage halts the workflow on failure (see [Join & gate](#join--gate-semantics)) |
| `fan_out` | list of branches | `[]` | Makes this a fan-out stage |

### Branch (`FanTask`) fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `brief` | string | *required* | The prompt for this branch (supports `{task}` / `{prev.summary}`) |
| `role` | string | — | Per-branch vendor-resolution key and router `kind`; falls back to the stage `role` |
| `vendor` | string | — | Pins this branch to a vendor outright |

A branch with no `brief` is a spec error (`each fan_out branch requires a 'brief'`).

## Vendor resolution (per branch)

Each branch resolves its vendor **independently**, with the same precedence as a sequential
stage:

```
branch.vendor  >  profile[branch.role or stage.role]  >  router(candidates, kind=role)  >  default_vendor
```

1. **`branch.vendor`** — an explicit pin always wins.
2. **Profile lookup** — `profile.roles[branch.role]`, falling back to `profile.roles[stage.role]`.
   A value of `auto` (or absent) defers to the router.
3. **Router** — if a `Router` and `--candidates` are supplied, `router.choose(candidates, kind=role)`
   picks by the active strategy (`weighted_quota`, `least_used`, …). Because branches resolve
   one after another and each records to the ledger, the router **naturally spreads** branches
   across vendors.
4. **Default** — `--vendor` / `default_vendor`, else `echo`.

Any resolved vendor whose CLI is not installed falls back to `echo` (the offline mock), so
fan-out workflows run end-to-end in CI with zero credentials.

This is what lets one fan-out stage land branch 0 on Claude, branch 1 on Codex, and branch 2
on Antigravity — under one policy, one ledger.

## Governance & ledger inheritance

Every branch is launched through the same `run()` path as any other stage, so it inherits:

- **The deny-policy** — the run's `--policy` is applied to each branch (preflight static scan
  + the vendor's native deny hook / execpolicy). A branch that trips the policy comes back
  `blocked=True`.
- **The usage ledger** — each branch records `requests` and `est_cost` to the shared ledger,
  so fan-out spend rolls into the same totals the router balances on. `WorkflowResult.cost_usd`
  sums every branch.

There is no "ungoverned subagent" escape hatch: a branch is just a governed worker like any
other. See [CAPABILITY-MATRIX.md](CAPABILITY-MATRIX.md) for what each governance layer guarantees.

## Join & gate semantics

After all branches in a stage have run:

- **Join** — their summaries are concatenated, each labelled with its result role, into the
  next stage's `{prev.summary}`:

  ```
  [implement[0]] <branch 0 summary>
  [implement[1]] <branch 1 summary>
  [implement[2]] <branch 2 summary>
  ```

- **Gate** — if the stage has `gate: true` and gates are enforced, the workflow **halts after
  the join** when *any* branch returned non-zero **or** was blocked. All branches in the stage
  still run (the gate trips on the group, not mid-fan-out); later stages are skipped and
  `WorkflowResult.halted` is `True`. Disable with `--no-gate`.

The join always happens, even when the gate trips, so a halted run's last stage still carries
every branch's partial summary for inspection.

## Execution model

Branches run **concurrently** on a bounded thread pool, but the run stays deterministic. The
trick is a two-phase split:

1. **Assign (sequential, deterministic).** Each branch's vendor is resolved one at a time, and
   its *request* is recorded to the ledger immediately — so `round_robin` / `least_used` spread
   each subsequent branch across vendors exactly as in a sequential pipeline.
2. **Execute (concurrent).** The resolved briefs run on a pool of up to `max_parallel` workers
   (default 8; a single branch or `max_parallel=1` runs inline with no threads). Each branch's
   *actual cost* is recorded when it finishes. Splitting request-vs-cost recording means the
   ledger nets exactly one request + the real cost per branch — no double-counting.

| Property | Behavior |
|---|---|
| Branch execution | Concurrent, bounded by `--max-parallel` (default 8) |
| Wall-clock | ≈ slowest branch (4 × 0.3 s branches: ~0.3 s vs ~1.2 s sequential) |
| Vendor assignment | Sequential → deterministic spread |
| Result / join / gate order | Re-ordered to declaration order → deterministic |
| Ledger totals | Order-independent (`flock`-guarded append) → deterministic |
| `on_event` streaming | Serialized so concurrent branch lines don't interleave mid-line |

Cost-based strategies (`least_used`, `weighted_quota`) spread on *request* count within a
fan-out stage, since a branch's cost isn't known until it finishes — inherent to running them at
once. Across stages and runs, the real costs are on the ledger and balance as usual.

## CLI

Fan-out needs no new flags — it is a property of the workflow YAML:

```bash
# Route branches across vendors by remaining quota:
jailbird run --workflow workflows/fan-out.yaml \
  --task "add three endpoints" \
  --candidates claude codex antigravity --strategy weighted_quota

# Or run fully offline on the echo mock (no credentials):
jailbird run --workflow workflows/fan-out.yaml --task "demo" --vendor echo
```

Relevant `jailbird run` flags: `--workflow`, `--task`, `--profile`, `--policy`, `--candidates`,
`--strategy`, `--no-gate`, `--ledger`, and `--max-parallel` (max branches to run at once;
default 8, `1` = sequential).

### Example run (offline, `echo`)

```
$ jailbird run --workflow workflows/fan-out.yaml \
    --task "add healthz/readyz/metrics endpoints" --vendor echo
...
[design]       vendor=echo rc=0 blocked=False $0.0100
[implement[0]] vendor=echo rc=0 blocked=False $0.0100
[implement[1]] vendor=echo rc=0 blocked=False $0.0100
[implement[2]] vendor=echo rc=0 blocked=False $0.0100
[qa]           vendor=echo rc=0 blocked=False $0.0100
halted=False total=$0.0500
```

Each branch appears as its own `role[i]` line; the QA stage's prompt receives the joined
`[implement[0]] done / [implement[1]] done / [implement[2]] done` summary.

## Programmatic API

```python
from jailbird.workflow.spec import Workflow, Stage, FanTask, Profile
from jailbird.workflow.pipeline import run_workflow

wf = Workflow(name="t", stages=[
    Stage(role="design", brief="design {task}"),
    Stage(role="implement", gate=True, fan_out=[
        FanTask(brief="part 1: {prev.summary}"),
        FanTask(brief="part 2: {prev.summary}", vendor="codex"),
        FanTask(brief="part 3: {prev.summary}", role="qa"),  # resolves via profile['qa']
    ]),
])

result = run_workflow(
    wf, "add three endpoints",
    profile=Profile({"implement": "claude", "qa": "antigravity"}),
    candidate_vendors=["claude", "codex", "antigravity"],
    default_vendor="echo",
    max_parallel=8,            # branches per fan-out stage to run at once (1 = sequential)
)

for s in result.stages:           # design, implement[0], implement[1], implement[2]
    print(s.role, s.vendor, s.returncode, s.blocked, s.cost_usd)
print(result.halted, result.cost_usd)
```

`run_workflow` flattens branches into `WorkflowResult.stages` as individual `StageResult`s with
roles `"<stage.role>[<i>]"`. `WorkflowResult.cost_usd` sums all of them; `WorkflowResult.halted`
reflects a tripped fan-out (or sequential) gate.

## Interpolation

Branch briefs support the same placeholders as sequential stages:

- `{task}` — the top-level task text passed to `--task` / `run_workflow(..., task_text)`.
- `{prev.summary}` — the **previous stage's** joined summary. All branches in a fan-out stage
  see the *same* `{prev.summary}` (the stage before them); they do not see each other's output.

## Honest limitations

- **Thread pool, not processes.** Branches run on a `ThreadPoolExecutor`; the work is the
  subprocess each branch spawns (the vendor CLI), so the GIL is not the bottleneck. `max_parallel`
  bounds concurrent vendor subprocesses — size it to your rate limits.
- **Cost-based spread is per-request within a stage.** `least_used` / `weighted_quota` can't
  balance on cost *inside* one fan-out stage because branch costs aren't known until they finish
  (see [Execution model](#execution-model)); they balance on request count there and on real cost
  everywhere else.
- **No cross-branch communication.** Branches in the same stage are independent and cannot read
  each other's results — that is the point. If a branch needs another's output, make them
  separate sequential stages.
- **Single-level.** A branch is a single governed run, not itself a sub-workflow; fan-out does
  not nest. (A model *running inside* a branch may still use its own vendor-native subagents —
  jailbird governs the worker, not the agent's internal delegation.)
- **Gate is all-or-nothing per stage.** A fan-out gate halts if *any* branch fails; there is no
  per-branch "continue on the survivors" mode yet.

## Testing

Fan-out is covered offline by the `echo` mock:

- `tests/test_workflow_spec.py` — YAML parsing, branch validation, `resolve_fan_vendor`.
- `tests/test_pipeline.py` — every branch runs, gate-halts on a failing branch, joined summary
  feeds the next stage, per-branch vendor pinning, **declaration-order determinism under the
  pool**, **`max_parallel=1` sequential mode**, **real concurrency** (timed: 6 branches run on
  the pool in a fraction of the serialized wall-clock), and **ledger accounting** (one request +
  the real cost per branch, even when a branch fails under a gate).
- `tests/test_examples.py` — `workflows/fan-out.yaml` and `examples/04-parallel-fan-out/` parse
  as part of the preset sweep.
- `tests/test_run_scripts.py` — `examples/04-parallel-fan-out/run.sh` is executed end-to-end in
  CI (PATH-stripped so it runs fully offline on `echo`).

```bash
ruff check . && mypy jailbird && pytest -q
```

## See also

- [README › Compose](../README.md#compose) — the workflow/profile model.
- [CAPABILITY-MATRIX.md](CAPABILITY-MATRIX.md) — what each governance layer guarantees.
- `workflows/fan-out.yaml` — the worked example used above.
- `examples/04-parallel-fan-out/` — a runnable example (design → 3 parallel branches → QA),
  executed offline in CI via `run.sh`.
