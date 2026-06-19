from __future__ import annotations
from pathlib import Path
from jailbird.govern.compile import compile_policy
from jailbird.govern.merge import deep_merge, load_structured, dump_structured
from jailbird.policy import Policy

def scope_dir(scope: str, base: str) -> str:
    if scope == "project":
        return base
    if scope == "user":
        return str(Path.home())
    if scope == "system":
        return "/etc/jailbird"  # documented: tamper-resistant tier (needs elevated install)
    raise ValueError(f"unknown scope '{scope}'")

def _render(art, existing: str) -> str:
    if not art.merge or art.fmt == "text":
        return art.content
    merged = deep_merge(load_structured(existing, art.fmt), load_structured(art.content, art.fmt))
    return dump_structured(merged, art.fmt)

def apply(policy: Policy, vendors: list[str], scope: str = "project", base: str = ".",
          dry_run: bool = False, remove: bool = False) -> list[str]:
    root = Path(scope_dir(scope, base))
    touched: list[str] = []
    for _vendor, arts in compile_policy(policy, vendors, scope).items():
        for art in arts:
            target = root / art.path
            touched.append(str(target))
            if dry_run:
                continue
            if remove:
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text() if target.exists() else ""
            target.write_text(_render(art, existing))
    return touched

def check(policy: Policy, vendors: list[str], scope: str = "project", base: str = ".") -> list[str]:
    root = Path(scope_dir(scope, base))
    drifted: list[str] = []
    for _vendor, arts in compile_policy(policy, vendors, scope).items():
        for art in arts:
            target = root / art.path
            if not target.exists():
                drifted.append(str(target))
                continue
            existing = target.read_text()
            if _render(art, existing) != existing:
                drifted.append(str(target))
    return drifted
