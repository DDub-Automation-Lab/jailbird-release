"""A deterministic fake coding-agent CLI for offline demos and CI.

Emits stream-json compatible with EchoAdapter.parse_stream. With --policy it
self-enforces (simulating a native PreToolUse hook): a prompt containing
"TRIGGER_DENY:<tool>" causes that tool to be blocked instead of run.
A prompt containing "TRIGGER_FAIL" exits with returncode 3 (simulates a
build/test failure for exercising enforcing gates).
"""
from __future__ import annotations
import argparse
import json
import sys

def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--policy", default=None)
    args = ap.parse_args(argv)

    emit({"type": "system", "subtype": "init", "model": "echo-1"})

    if "TRIGGER_FAIL" in args.prompt:
        emit({"type": "assistant", "text": "simulated failure"})
        emit({"type": "result", "subtype": "error", "total_cost_usd": 0.0, "result": "failed"})
        return 3

    if "TRIGGER_BLOCK" in args.prompt:
        emit({"type": "user", "is_error": True,
              "text": "BLOCKED by jailbird policy (simulated mid-run block)"})
        emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0, "result": "blocked"})
        return 0

    denied = None
    if args.prompt.startswith("TRIGGER_DENY:"):
        tool = args.prompt.split(":", 1)[1].strip()
        if args.policy:
            from jailbird.policy import Policy
            from jailbird.types import ToolCall
            verdict = Policy.from_yaml(args.policy).evaluate(ToolCall(name=tool))
            if verdict.decision.value == "deny":
                denied = (tool, verdict.reason)
        if denied:
            emit({"type": "user", "is_error": True,
                  "text": f"BLOCKED by jailbird policy: {denied[0]} ({denied[1]})"})
        else:
            emit({"type": "tool_use", "name": tool, "summary": "(simulated)"})
    else:
        emit({"type": "tool_use", "name": "Bash", "summary": "echo hi"})
        emit({"type": "assistant", "text": f"echo: {args.prompt}"})

    emit({"type": "result", "subtype": "success", "total_cost_usd": 0.01,
          "result": "done" if not denied else "blocked"})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
