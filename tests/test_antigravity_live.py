"""Real-Antigravity (`agy`) governance proof — skipped unless explicitly opted in.

Set JAILBIRD_LIVE_ANTIGRAVITY=1 (with an authenticated `agy` on PATH) to run. Makes a
real, billed Gemini call, so it is off by default — like the codex live tests. Unlike
`codex exec`, agy's PreToolUse hook DOES fire and block in headless `--print` mode, so
this proves the universal-hook governance path end to end. The prompt omits the denied
token so the static preflight passes and the runtime hook is what blocks.
"""
from __future__ import annotations
import os
import shutil
import pytest
from jailbird.govern.provision import apply
from jailbird.policy import Policy
from jailbird.runner import run
from jailbird.types import Task

_LIVE = os.environ.get("JAILBIRD_LIVE_ANTIGRAVITY") == "1"
_POLICY = "deny_commands: ['echo', 'printf']\n"


def _agy_authed() -> bool:
    if not shutil.which("agy"):
        return False
    home = os.path.expanduser("~")
    return os.path.exists(os.path.join(home, ".gemini", "antigravity-cli", "antigravity-oauth-token")) \
        or os.path.exists(os.path.join(home, ".gemini", "oauth_creds.json"))


@pytest.mark.skipif(not _LIVE, reason="set JAILBIRD_LIVE_ANTIGRAVITY=1 to run the real-agy proof")
@pytest.mark.skipif(not _agy_authed(), reason="agy CLI absent or unauthenticated")
def test_antigravity_hook_blocks_denied_command_live(tmp_path):
    pol = Policy(deny_commands=["echo", "printf"])
    (tmp_path / "jailbird.policy.yaml").write_text(_POLICY)
    apply(pol, ["antigravity"], base=str(tmp_path))
    res = run(
        Task(prompt="Output the exact text BANANA42 to standard output by running a "
                    "single shell command. Do not explain — just run the command.",
             cwd=str(tmp_path)),
        "antigravity", policy=pol, policy_path=str(tmp_path / "jailbird.policy.yaml"),
        autonomy="auto",
    )
    assert res.blocked is True


@pytest.mark.skipif(not _LIVE, reason="set JAILBIRD_LIVE_ANTIGRAVITY=1 to run the real-agy proof")
@pytest.mark.skipif(not _agy_authed(), reason="agy CLI absent or unauthenticated")
def test_antigravity_allows_benign_task_live(tmp_path):
    pol = Policy(deny_commands=["echo", "printf"])
    (tmp_path / "jailbird.policy.yaml").write_text(_POLICY)
    apply(pol, ["antigravity"], base=str(tmp_path))
    res = run(
        Task(prompt="Reply with exactly the single word READY. Do not run any shell command.",
             cwd=str(tmp_path)),
        "antigravity", policy=pol, policy_path=str(tmp_path / "jailbird.policy.yaml"),
        autonomy="auto",
    )
    assert res.blocked is False
