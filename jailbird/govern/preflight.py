from __future__ import annotations
from jailbird.policy import Policy
from jailbird.types import ToolCall, PolicyVerdict, Decision

class PreflightError(Exception):
    pass

def preflight(policy: Policy, brief: str, argv: list[str]) -> PolicyVerdict:
    haystack = brief + " " + " ".join(argv)
    # Command patterns: evaluate the combined text as a pseudo-command.
    v = policy.evaluate(ToolCall(name="<preflight>", command=haystack))
    if v.decision is Decision.DENY:
        return v
    # Tool-name patterns: check each whitespace token against deny_tools.
    for token in haystack.split():
        tv = policy.evaluate(ToolCall(name=token))
        if tv.decision is Decision.DENY:
            return tv
    return PolicyVerdict(Decision.ALLOW)
