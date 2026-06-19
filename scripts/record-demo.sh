#!/usr/bin/env bash
# Drives the offline demo cast for the README (govern + route). Sanitized
# prompt, no personal paths. Run from the repo root inside the project venv.
# All beats run on the echo vendor / local ledger — zero credentials.
set -uo pipefail
export PS1=''
demo() { printf '\n\033[32m$\033[0m %s\n' "$*"; sleep 1.2; eval "$*"; sleep 1.6; }

printf '# jailbird — governed & usage-routed, offline on echo (zero credentials)\n'

# Beat 1 — govern: one policy compiles to each vendor; a denied command is refused
demo 'jailbird apply --policy examples/02-governed-deny/no-push.policy.yaml --vendors claude codex antigravity --dry-run'
demo 'jailbird run --vendor echo --policy examples/02-governed-deny/no-push.policy.yaml --prompt "now git push origin main" --ledger /tmp/jb-run-ledger.jsonl || echo "REFUSED (exit $?)"'

# Beat 2 — route: usage-balanced pick from the ledger
demo 'jailbird route --vendors claude codex antigravity --no-require-cli --strategy least_used --ledger /tmp/jb-cast-ledger.jsonl'

sleep 1.2
