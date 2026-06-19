from __future__ import annotations
import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from jailbird.types import ToolCall, PolicyVerdict, Decision

def _glob_to_regex(pattern: str) -> re.Pattern:
    # Normalize the pattern's whitespace, convert globs, then let any
    # literal space match a whitespace run (so "git push" matches "git   push").
    # Spaces are split out before re.escape so that each word is escaped
    # individually and then joined with \s+, which is portable across Python
    # versions (re.escape escapes spaces in 3.14+).
    norm = re.sub(r"\s+", " ", pattern.strip())
    parts = norm.split("*")
    rx_parts = []
    for p in parts:
        words = p.split(" ")
        rx_parts.append(r"\s+".join(re.escape(w) for w in words))
    rx = ".*".join(rx_parts)
    return re.compile(rx, re.IGNORECASE)

@dataclass
class Policy:
    deny_tools: list[str] = field(default_factory=list)
    deny_commands: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    mode: str = "deny"

    @classmethod
    def from_dict(cls, d: dict) -> "Policy":
        return cls(
            deny_tools=list(d.get("deny_tools", [])),
            deny_commands=list(d.get("deny_commands", [])),
            deny_paths=list(d.get("deny_paths", [])),
            mode=d.get("mode", "deny"),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "Policy":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls.from_dict(data)

    def evaluate(self, call: ToolCall) -> PolicyVerdict:
        for pat in self.deny_tools:
            if fnmatch.fnmatch(call.name, pat):
                return PolicyVerdict(Decision.DENY, f"tool '{call.name}' denied", pat)
        if call.command:
            norm = re.sub(r"\s+", " ", call.command.strip())
            for pat in self.deny_commands:
                if _glob_to_regex(pat).search(norm):
                    return PolicyVerdict(Decision.DENY, f"command matches '{pat}'", pat)
        for path in call.paths:
            for pat in self.deny_paths:
                expanded = pat.replace("~", str(Path.home()))
                if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, expanded):
                    return PolicyVerdict(Decision.DENY, f"path '{path}' denied", pat)
        return PolicyVerdict(Decision.ALLOW)
