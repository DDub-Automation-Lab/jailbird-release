#!/usr/bin/env python3
"""Render the offline demo cast (assets/demo.svg).

Builds an asciicast (v2) from the deterministic, offline-reproducible beats
that scripts/record-demo.sh runs on the echo vendor — govern (one policy ->
each vendor's native config, then a denied `git push` refused at preflight)
and usage-balanced routing — then renders it to a self-contained animated SVG
with termtosvg. Generated this way (rather than a live capture) so it is
deterministic and leaks no terminal/host state. Run from the repo root:

    python scripts/gen-demo-cast.py
"""
import json
import subprocess
import tempfile

events = []
t = 0.0
SPEED = 1.7  # >1 slows the whole animation (typing + pauses) uniformly


def emit(s):
    events.append([round(t, 3), "o", s])


def wait(dt):
    global t
    t += dt * SPEED


def typeline(s, cps=55):
    for ch in s:
        emit(ch)
        wait(1.0 / cps)


E = chr(27)
GREEN = E + "[32m"
R = E + "[0m"
DIM = E + "[90m"
CYAN = E + "[36m"
RED = E + "[31m"
MAG = E + "[35m"
BOLD = E + "[1m"


def out(s):
    emit(s + "\r\n")


def prompt(lines):
    emit(GREEN + "$ " + R)
    typeline(lines[0])
    emit("\r\n")
    for cont in lines[1:]:
        typeline("    " + cont)
        emit("\r\n")
    wait(0.35)


out(DIM + "# jailbird - governed & usage-routed, offline on echo (zero credentials)" + R)
wait(0.7)

prompt(["jailbird apply --policy examples/02-governed-deny/no-push.policy.yaml \\",
        "--vendors claude codex antigravity --dry-run"])
for p in [".claude/settings.json", ".codex/config.toml", ".codex/rules/jailbird.rules", ".agents/hooks.json"]:
    out(CYAN + "DRYRUN " + R + p)
    wait(0.14)
wait(0.9)

prompt(["jailbird run --vendor echo \\",
        "--policy examples/02-governed-deny/no-push.policy.yaml \\",
        "--prompt \"now git push origin main\""])
wait(0.25)
out(RED + BOLD + "REFUSED" + R + RED + ": preflight refused: command matches 'git push'" + R)
out(DIM + "(exit 2)" + R)
wait(1.1)

prompt(["jailbird route --vendors claude codex antigravity \\",
        "--no-require-cli --strategy least_used"])
wait(0.25)
out("chosen: " + MAG + BOLD + "codex" + R + DIM + "  (strategy=least_used)" + R)
out(DIM + "  claude:      requests=6  est_cost=0.78" + R)
out("  codex:       requests=1  est_cost=0.0")
out(DIM + "  antigravity: requests=3  est_cost=0.0" + R)
wait(1.8)

header = {"version": 2, "width": 78, "height": 23,
          "timestamp": 0, "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"}}
with tempfile.NamedTemporaryFile("w", suffix=".cast", delete=False) as f:
    f.write(json.dumps(header) + "\n")
    for e in events:
        f.write(json.dumps(e) + "\n")
    cast = f.name

subprocess.run(["termtosvg", "render", cast, "assets/demo.svg", "-t", "window_frame"], check=True)
print("wrote assets/demo.svg (", len(events), "events,", round(t, 2), "s )")
