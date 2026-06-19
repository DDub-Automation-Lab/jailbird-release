import json
import subprocess
import sys
from jailbird.adapters import get_adapter
from jailbird.types import Task

def test_echo_registered():
    a = get_adapter("echo")
    assert a.name == "echo"

def test_echo_build_argv_runs_module():
    a = get_adapter("echo")
    argv = a.build_argv(Task(prompt="hello"), autonomy="build", config_dir="/tmp/x")
    assert argv[0] == sys.executable and "jailbird.adapters.echo_agent" in argv

def test_echo_parse_stream_maps_events():
    a = get_adapter("echo")
    line = json.dumps({"type": "result", "total_cost_usd": 0.02, "result": "done"})
    ev = a.parse_stream(line)
    assert ev.kind == "result" and ev.cost_usd == 0.02

def test_echo_agent_emits_stream_and_cost():
    out = subprocess.run(
        [sys.executable, "-m", "jailbird.adapters.echo_agent", "--prompt", "hi"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    types = [json.loads(ln)["type"] for ln in out]
    assert types[0] == "system" and types[-1] == "result"
    assert any(json.loads(ln).get("type") == "assistant" for ln in out)

def test_echo_agent_self_enforces_policy(tmp_path):
    pol = tmp_path / "p.yaml"
    pol.write_text("deny_tools: ['mcp__broker__place_order']\n")
    out = subprocess.run(
        [sys.executable, "-m", "jailbird.adapters.echo_agent",
         "--prompt", "TRIGGER_DENY:mcp__broker__place_order", "--policy", str(pol)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "BLOCKED by jailbird policy" in out
