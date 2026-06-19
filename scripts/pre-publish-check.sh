#!/usr/bin/env bash
# Layer 5 — run ONCE before the first public push. Deep checks over the whole repo + history.
# Exits non-zero (and tells you what tripped) if anything is unsafe to publish.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
fail=0

echo "== 1/5 full-history secret/PII scan (every added line, all commits) =="
if ! python3 .githooks/secret-scan.py diff HEAD; then fail=1; fi

echo "== 2/5 working-tree scan (current tracked files) =="
if ! git ls-files -z | xargs -0 python3 .githooks/secret-scan.py files; then fail=1; fi

echo "== 3/5 author emails — must all be a GitHub noreply =="
if git log --format='%ae' | grep -vE 'users\.noreply\.github\.com$' | grep -q .; then
  echo "  FAIL: non-noreply author(s):" ; git log --format='  %h %an <%ae>' | grep -vE 'noreply'
  fail=1
else
  echo "  OK"
fi

echo "== 4/5 personal-coupling scrub test =="
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
if ! "$PY" -m pytest tests/test_no_personal_coupling.py -q >/dev/null 2>&1; then
  echo "  FAIL: scrub test"; fail=1
else
  echo "  OK"
fi

echo "== 5/5 tracked files (eyeball this list — nothing here should be private) =="
git ls-files

echo
if [ "$fail" -ne 0 ]; then
  echo "NOT SAFE TO PUBLISH — fix the items above and re-run."
  exit 1
fi
echo "ALL CLEAR. To publish (after choosing the home: your org vs personal account):"
echo "  # optional: squash to a clean history first  ->  git checkout --orphan release && git commit -m 'Initial release'"
echo "  gh repo create <owner>/jailbird --public --source . --remote origin --push"
