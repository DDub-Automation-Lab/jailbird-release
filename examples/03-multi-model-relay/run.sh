#!/usr/bin/env bash
# Multi-model collaboration: Claude designs -> Codex implements -> Antigravity QAs,
# governed + usage-routed. Runs on echo offline; set real CLIs to go live.
set -euo pipefail
jailbird run --workflow design-build-qa.workflow.yaml \
  --profile jailbird.profile.yaml \
  --task "add a /healthz endpoint with a test" \
  --vendor echo \
  --ledger .jailbird/ledger.jsonl
