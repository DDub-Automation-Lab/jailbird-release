#!/usr/bin/env python3
"""jailbird repo secret/PII guard — shared by the git hooks and the pre-publish check.

This is a deny-hook for the repository itself: it refuses to let secret material or
personal-coupling tokens reach a public remote. Pure stdlib, no install required.

Usage:
  secret-scan.py files <path> [<path> ...]   # scan the given files' current contents
  secret-scan.py diff  <git-range-or-ref>    # scan ADDED lines across a commit range
                                             #   (e.g. "A..B", or a single ref = all ancestors)

Exits 0 if clean, 1 if any match is found (printing file:line: matched-token).
"""
from __future__ import annotations

import re
import subprocess
import sys

# High-confidence secret material — must NEVER appear anywhere, including the denylist files.
SECRET = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{35}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN[ A-Z]*PRIVATE KEY-----"
    r"|Bearer [A-Za-z0-9._-]{20,}"
)

# Personal-coupling / PII — repo-specific tokens that must not leak into a public repo.
# Mirrors tests/test_no_personal_coupling.py plus the owner's personal email.
PII = re.compile(
    r"cortex|hermes|robinhood|velo|trading|dwhite|tailscale|job\.py|mqtt|telegram|discord"
    r"|/Users/|~/docs",
    re.IGNORECASE,
)

# Files that legitimately contain the PII patterns (the denylist itself). Secret patterns are
# still enforced in these files — only the PII check is relaxed.
PII_ALLOW = (
    "tests/test_no_personal_coupling.py",
    ".githooks/secret-scan.py",
    "scripts/pre-publish-check.sh",
)

SCAN_SUFFIXES = {
    ".py", ".md", ".yaml", ".yml", ".toml", ".sh", ".json", ".cfg", ".txt", ".ini", ".env",
    ".js", ".ts", ".svg", "",  # "" = extensionless (run.sh-style, LICENSE); .svg = demo recordings
}


def _suffix(path: str) -> str:
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:] if dot > slash else ""


def _check(path: str, lineno: int, text: str, offenders: list[str]) -> None:
    m = SECRET.search(text)
    if m:
        offenders.append(f"{path}:{lineno}: SECRET {m.group(0)[:12]}…")
    if not path.endswith(PII_ALLOW):
        p = PII.search(text)
        if p:
            offenders.append(f"{path}:{lineno}: PII '{p.group(0)}'")


def scan_files(paths: list[str]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        if not path or _suffix(path) not in SCAN_SUFFIXES:
            continue
        try:
            with open(path, "r", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    _check(path, i, line, offenders)
        except (FileNotFoundError, IsADirectoryError):
            continue
    return offenders


def scan_diff(rangespec: str) -> list[str]:
    out = subprocess.run(
        ["git", "log", "-p", "--no-color", rangespec],
        capture_output=True, text=True,
    ).stdout
    offenders: list[str] = []
    cur = "<unknown>"
    lineno = 0
    for raw in out.splitlines():
        if raw.startswith("+++ b/"):
            cur = raw[6:]
            lineno = 0
            continue
        if raw.startswith("@@"):
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            lineno += 1
            _check(cur, lineno, raw[1:], offenders)
    return offenders


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("files", "diff"):
        print(__doc__, file=sys.stderr)
        return 2
    offenders = scan_files(argv[1:]) if argv[0] == "files" else scan_diff(argv[1])
    if offenders:
        print("secret-scan: BLOCKED — potential secret/PII found:", file=sys.stderr)
        for o in offenders:
            print(f"  {o}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
