from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class FanTask:
    """One independent branch of a fan-out stage. Routed and governed on its own,
    so each branch can land on a different vendor while sharing the run's policy
    and usage ledger. ``role`` (falls back to the stage's role) drives vendor
    resolution and router ``kind``; ``vendor`` pins it outright."""
    brief: str = ""
    role: str | None = None
    vendor: str | None = None

@dataclass
class Stage:
    role: str
    brief: str = ""
    vendor: str | None = None
    autonomy: str = "build"
    gate: bool = False
    fan_out: list[FanTask] = field(default_factory=list)

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
            fan_raw = s.get("fan_out") or []
            if not isinstance(fan_raw, list):
                raise ValueError("stage 'fan_out' must be a list of branches")
            fan = []
            for f in fan_raw:
                if not f.get("brief"):
                    raise ValueError("each fan_out branch requires a 'brief'")
                fan.append(FanTask(brief=f["brief"], role=f.get("role"),
                                   vendor=f.get("vendor")))
            stages.append(Stage(role=s["role"], brief=s.get("brief", ""),
                                vendor=s.get("vendor"), autonomy=s.get("autonomy", "build"),
                                gate=bool(s.get("gate", False)), fan_out=fan))
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

def resolve_fan_vendor(task: FanTask, stage: Stage, profile: Profile) -> str | None:
    """Vendor for one fan-out branch: branch pin > profile[branch.role or stage.role].
    A None/``auto`` result hands the choice to the router (same as a sequential stage)."""
    if task.vendor:
        return task.vendor
    return profile.roles.get(task.role or stage.role)
