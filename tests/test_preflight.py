import pytest
from jailbird.govern.preflight import preflight, PreflightError
from jailbird.policy import Policy
from jailbird.types import Decision

POL = Policy(deny_commands=["git push"], deny_tools=["mcp__*__place_*"])

def test_flags_denied_command_in_brief():
    v = preflight(POL, brief="then git push to origin", argv=["claude", "-p", "x"])
    assert v.decision is Decision.DENY

def test_flags_denied_token_in_argv():
    v = preflight(POL, brief="ok", argv=["claude", "-p", "please mcp__broker__place_order now"])
    assert v.decision is Decision.DENY

def test_allows_clean():
    v = preflight(POL, brief="add tests", argv=["claude", "-p", "add tests"])
    assert v.decision is Decision.ALLOW

def test_raises_helper():
    with pytest.raises(PreflightError):
        v = preflight(POL, brief="git push", argv=[])
        if v.decision is Decision.DENY:
            raise PreflightError(v.reason)
