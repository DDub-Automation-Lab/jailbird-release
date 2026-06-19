#!/usr/bin/env bash
# Enable the repo's secret-leak guard hooks. Run once after cloning.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
git -C "$ROOT" config core.hooksPath .githooks
chmod +x "$ROOT"/.githooks/pre-commit "$ROOT"/.githooks/pre-push "$ROOT"/.githooks/secret-scan.py 2>/dev/null || true
echo "Installed: core.hooksPath -> .githooks (pre-commit + pre-push secret/PII guards active)."
