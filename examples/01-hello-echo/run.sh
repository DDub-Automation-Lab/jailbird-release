#!/usr/bin/env bash
# Quickstart: one governed worker, fully offline (no credentials).
set -euo pipefail
jailbird run --vendor echo --prompt "summarize what jailbird does" --ledger .jailbird/ledger.jsonl
