import os
import subprocess
import sys
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENV_BIN = pathlib.Path(sys.executable).parent

@pytest.mark.parametrize("script", [
    "examples/01-hello-echo/run.sh",
    "examples/02-governed-deny/run.sh",
    "examples/03-multi-model-relay/run.sh",
    "examples/04-parallel-fan-out/run.sh",
])
def test_example_run_scripts_offline(script):
    if not (VENV_BIN / "jailbird").exists():
        pytest.skip("jailbird console script not on venv PATH")
    sp = ROOT / script
    # PATH = venv bin + core only; excludes ~/.local/bin and /opt/homebrew/bin where the real
    # claude/codex/agy live, so the relay falls back to echo and every example runs offline.
    env = {"PATH": f"{VENV_BIN}:/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp")}
    r = subprocess.run(["bash", sp.name], cwd=str(sp.parent), env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{script} -> {r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
