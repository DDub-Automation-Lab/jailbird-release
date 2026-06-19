# tests/test_no_personal_coupling.py
import re
import pathlib

FORBIDDEN = re.compile(
    r"cortex|hermes|robinhood|velo|trading|dwhite|tailscale|job\.py|mqtt|telegram|discord"
    r"|/Users/|~/docs",
    re.IGNORECASE,
)
SCAN_EXT = {".py", ".md", ".yaml", ".yml", ".toml", ".sh", ".json", ".cfg", ".txt", ".svg"}
# Skipped: VCS/build caches, and git-ignored internal dirs that never publish
# (PlannedWork = audit/planning docs; tools = reusable audit toolkit kept in shared-tools).
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache",
             "jailbird.egg-info", "PlannedWork", "tools"}
# Files that legitimately contain the denylist patterns: this test and the secret-leak guards.
ALLOWLIST = {"test_no_personal_coupling.py", "secret-scan.py", "pre-publish-check.sh"}


def test_no_personal_coupling_tokens():
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for p in root.rglob("*"):
        if p.is_dir() or p.suffix not in SCAN_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name in ALLOWLIST:
            continue  # the denylist patterns live here by design
        text = p.read_text(errors="ignore")
        for m in FORBIDDEN.finditer(text):
            offenders.append(f"{p}: {m.group(0)}")
    assert not offenders, "personal-coupling tokens found:\n" + "\n".join(offenders)
