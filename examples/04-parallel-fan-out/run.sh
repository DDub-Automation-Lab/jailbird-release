#!/usr/bin/env bash
# Parallel fan-out: design once, implement three independent parts concurrently across
# vendors, then re-converge for QA. Branches run on a bounded pool (--max-parallel) and
# re-order to declaration order, so the run is deterministic. Runs on echo offline; set
# real CLIs (claude/codex/agy) to go live and spread branches across vendors.
set -euo pipefail
jailbird run --workflow fan-out.workflow.yaml \
  --profile jailbird.profile.yaml \
  --task "add healthz, readyz, and metrics endpoints with tests" \
  --vendor echo \
  --max-parallel 3 \
  --ledger .jailbird/ledger.jsonl
