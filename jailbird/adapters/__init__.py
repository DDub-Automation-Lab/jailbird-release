from __future__ import annotations
from jailbird.adapters.base import VendorAdapter
from jailbird.adapters.echo import EchoAdapter
from jailbird.adapters.claude import ClaudeAdapter
from jailbird.adapters.codex import CodexAdapter
from jailbird.adapters.antigravity import AntigravityAdapter

VENDORS: dict[str, type[VendorAdapter]] = {"echo": EchoAdapter, "claude": ClaudeAdapter,
                                            "codex": CodexAdapter,
                                            "antigravity": AntigravityAdapter}

def get_adapter(name: str) -> VendorAdapter:
    try:
        return VENDORS[name]()
    except KeyError:
        raise ValueError(f"unknown vendor '{name}'. known: {sorted(VENDORS)}")

def vendor_available(name: str) -> bool:
    """True if ``name`` is a registered vendor whose CLI can run here (echo is always
    available; others require their binary on PATH). False for unknown vendors. Resolves
    by the adapter's real binary, so antigravity checks ``agy``, not ``antigravity``."""
    try:
        return get_adapter(name).is_available()
    except ValueError:
        return False
