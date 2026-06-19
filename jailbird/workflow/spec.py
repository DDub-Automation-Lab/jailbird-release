from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class Stage:
    role: str
    brief: str = ""
    vendor: str | None = None
    autonomy: str = "build"
    gate: bool = False

@dataclass
class Workflow:
    name: str
    stages: list[Stage]

    @classmethod
    def from_dict(cls, d: dict) -> "Workflow":
        if not d.get("name"):
            raise ValueError("workflow requires a 'name'")
        raw = d.get("stages")
        if not isinstance(raw, list) or not raw:
            raise ValueError("workflow requires a non-empty 'stages' list")
        stages = []
        for s in raw:
            if not s.get("role"):
                raise ValueError("each stage requires a 'role'")
            stages.append(Stage(role=s["role"], brief=s.get("brief", ""),
                                vendor=s.get("vendor"), autonomy=s.get("autonomy", "build"),
                                gate=bool(s.get("gate", False))))
        return cls(name=d["name"], stages=stages)

    @classmethod
    def from_yaml(cls, path: str) -> "Workflow":
        return cls.from_dict(yaml.safe_load(Path(path).read_text()) or {})

@dataclass
class Profile:
    roles: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(roles=dict((d or {}).get("roles", {})))

    @classmethod
    def from_yaml(cls, path: str) -> "Profile":
        return cls.from_dict(yaml.safe_load(Path(path).read_text()) or {})

    @classmethod
    def empty(cls) -> "Profile":
        return cls()

def resolve_vendor(stage: Stage, profile: Profile) -> str | None:
    if stage.vendor:
        return stage.vendor
    return profile.roles.get(stage.role)
