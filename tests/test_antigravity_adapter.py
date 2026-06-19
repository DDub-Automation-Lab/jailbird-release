import json
import sys
from jailbird.adapters import get_adapter
from jailbird.types import Task
from jailbird.policy import Policy

A = get_adapter("antigravity")


def test_registered_in_vendors():
    assert A.name == "antigravity"


def test_build_argv_print_mode_never_bypasses():
    argv = A.build_argv(Task(prompt="do a thing"), autonomy="auto", config_dir="/tmp/x")
    assert argv[0] == "agy"
    assert "--print" in argv
    assert argv[-1] == "do a thing"  # prompt is the trailing value of --print
    for bad in ("--dangerously-skip-permissions",):
        assert bad not in argv


def test_governance_emits_agents_hooks_json():
    arts = {a.path: a for a in A.governance_artifacts(Policy(deny_tools=["run_command"]),
                                                      scope="project")}
    hooks = json.loads(arts[".agents/hooks.json"].content)
    # top-level is a map of hook-name -> {PreToolUse: [...]}; find the jailbird entry
    entry = next(iter(hooks.values()))
    pre = entry["PreToolUse"][0]
    assert pre["hooks"][0]["command"] == \
        f"{sys.executable} -m jailbird.govern.hook --vendor antigravity"


def test_parse_hook_input_maps_toolcall_commandline():
    d = {"toolCall": {"name": "run_command", "args": {"CommandLine": "echo hi", "Cwd": "/x"}}}
    call = A.parse_hook_input(d)
    assert call.name == "run_command"
    assert call.command == "echo hi"


def test_deny_response_matches_decision_contract():
    out = json.loads(A.deny_response("nope"))
    assert out["decision"] == "deny"
    assert out["reason"] == "nope"


def test_parse_stream_plain_text_is_text_event():
    ev = A.parse_stream("Here is the answer.")
    assert ev is not None and ev.kind == "text" and ev.text == "Here is the answer."
