from __future__ import annotations
import argparse
import json
import os
import sys
from jailbird.adapters import get_adapter
from jailbird.policy import Policy
from jailbird.types import Decision

def _resolve_policy(path: str | None) -> Policy:
    candidate = path or os.environ.get("JAILBIRD_POLICY") or "jailbird.policy.yaml"
    if os.path.exists(candidate):
        return Policy.from_yaml(candidate)
    return Policy()  # empty policy = allow-all (fail-open is documented; sandbox is the hard layer)

def main(argv: list[str], stdin_text: str) -> tuple[int, str]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--policy", default=None)
    args = ap.parse_args(argv)
    adapter = get_adapter(args.vendor)
    try:
        event = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        return 0, ""
    call = adapter.parse_hook_input(event)
    verdict = _resolve_policy(args.policy).evaluate(call)
    if verdict.decision is Decision.DENY:
        _mark_blocked(verdict.reason)
        return 0, adapter.deny_response(f"BLOCKED by jailbird: {verdict.reason}")
    return 0, adapter.allow_response()

def _mark_blocked(reason: str) -> None:
    # Deterministic, vendor-agnostic block signal: the runner reads this file to set
    # RunResult.blocked. Needed because some CLIs (e.g. agy) reword the denial in prose
    # stdout, so matching the deny text is unreliable.
    sentinel = os.environ.get("JAILBIRD_BLOCK_SENTINEL")
    if not sentinel:
        return
    try:
        with open(sentinel, "a") as f:
            f.write(reason + "\n")
    except OSError:
        pass

if __name__ == "__main__":
    code, out = main(sys.argv[1:], sys.stdin.read())
    if out:
        sys.stdout.write(out)
    raise SystemExit(code)
