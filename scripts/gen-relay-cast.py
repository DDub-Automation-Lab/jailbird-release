#!/usr/bin/env python3
"""Render the real multi-vendor relay cast (assets/relay.svg).

This renders a CAPTURED transcript of a real `jailbird run --workflow
design-build-qa.yaml` executed once against the real CLIs (claude -> codex ->
antigravity) in an isolated throwaway directory (not this repo). The lines
below are trimmed from that genuine run: claude produced a design, codex wrote
text_utils.py + a pytest suite (9 passed), and antigravity's review found a
real regex-backreference bug. Rendered deterministically with termtosvg so it
leaks no terminal/host state. Run from the repo root:

    python scripts/gen-relay-cast.py
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
R = E + "[0m"
DIM = E + "[90m"
GREEN = E + "[32m"
BOLD = E + "[1m"
YEL = E + "[33m"
BLUE = E + "[34m"
CYAN = E + "[36m"
RED = E + "[31m"
MAG = E + "[35m"


def out(s):
    emit(s + "\r\n")


def prompt(lines):
    emit(GREEN + "$ " + R)
    typeline(lines[0])
    emit("\r\n")
    for cont in lines[1:]:
        typeline("    " + cont)
        emit("\r\n")
    wait(0.4)


out(DIM + "# jailbird - a real 3-vendor relay (claude -> codex -> antigravity)" + R)
wait(0.6)
prompt(["jailbird run --workflow design-build-qa.yaml --profile jailbird.profile.yaml \\",
        "--task \"add a slugify(text) function with a pytest test\""])
wait(0.4)

out(YEL + BOLD + "[design] claude" + R)
out(DIM + "  ## slugify(text) in text_utils.py - stdlib only (re, unicodedata):" + R)
out(DIM + "  normalize NFKD -> ascii, lowercase, re.sub(r\"[^a-z0-9]+\", sep), strip" + R)
out(DIM + "  edge cases: \"Cafe deja vu\"->\"cafe-deja-vu\", \"foo@@bar!!\"->\"foo-bar\", \"\"->\"\"" + R)
wait(1.0)

out(GREEN + BOLD + "[implement] codex" + R)
out(DIM + "  -> wrote text_utils.py + test_text_utils.py" + R)
out("  -> python -m pytest  " + GREEN + "9 passed" + R)
wait(1.0)

out(BLUE + BOLD + "[qa] antigravity" + R)
out(RED + "  found a real bug: " + R + DIM + "separator is re.sub's repl, so a separator" + R)
out(DIM + "  containing \\1 / \\g<1> is parsed as a backreference -> re.error" + R)
out(DIM + "  fix: re.sub(r\"[^a-z0-9]+\", lambda _: separator, ...). else production-ready." + R)
wait(1.1)

out("")
out(DIM + "[design]    " + R + "vendor=claude       rc=0  $0.1347")
out(DIM + "[implement] " + R + "vendor=codex        rc=0  $0.0000  " + DIM + "(tokens, not cost)" + R)
out(DIM + "[qa]        " + R + "vendor=antigravity  rc=0  $0.0000")
out(BOLD + "halted=False  total=$0.1347" + R)
wait(1.8)

header = {"version": 2, "width": 84, "height": 24,
          "timestamp": 0, "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"}}
with tempfile.NamedTemporaryFile("w", suffix=".cast", delete=False) as f:
    f.write(json.dumps(header) + "\n")
    for e in events:
        f.write(json.dumps(e) + "\n")
    cast = f.name

subprocess.run(["termtosvg", "render", cast, "assets/relay.svg", "-t", "window_frame"], check=True)
print("wrote assets/relay.svg (", len(events), "events,", round(t, 2), "s )")
