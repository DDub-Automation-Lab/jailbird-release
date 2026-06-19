from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"

@dataclass
class PolicyVerdict:
    decision: Decision
    reason: str = ""
    rule: str = ""

@dataclass
class Event:
    kind: str  # "init" | "text" | "tool" | "tool_error" | "result"
    text: str = ""
    tool: str = ""
    summary: str = ""
    cost_usd: float = 0.0
    is_error: bool = False
    raw: dict = field(default_factory=dict)

@dataclass
class ToolCall:
    name: str
    command: str = ""
    paths: list[str] = field(default_factory=list)
    raw_input: dict = field(default_factory=dict)

@dataclass
class ConfigArtifact:
    path: str
    content: str
    fmt: str = "json"  # "json" | "toml" | "text"
    merge: bool = True

@dataclass
class Task:
    prompt: str
    cwd: str = "."
    brief_path: str | None = None
