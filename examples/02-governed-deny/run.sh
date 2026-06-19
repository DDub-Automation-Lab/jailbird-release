#!/usr/bin/env bash
# Governance demo: the policy refuses a denied command at preflight, and the
# same policy compiles to each vendor's native deny config via `apply`.
set -euo pipefail
echo "## provisioning native governance config for all vendors (dry-run):"
jailbird apply --policy no-push.policy.yaml --vendors claude codex antigravity --dry-run
echo "## attempting a denied command (expect a preflight refusal, non-zero exit):"
jailbird run --vendor echo --policy no-push.policy.yaml --prompt "now git push origin main" \
  --ledger .jailbird/ledger.jsonl || echo "REFUSED as expected (exit $?)"
