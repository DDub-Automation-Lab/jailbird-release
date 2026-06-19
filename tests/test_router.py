import pytest
from jailbird.router.ledger import Ledger
from jailbird.router.quota import BudgetCapQuota
from jailbird.router.router import Router

def _router(tmp_path, strategy="weighted_quota"):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record("claude", est_cost=9.0)
    q = BudgetCapQuota({"claude": 10.0, "echo": 10.0}, led)
    return Router(led, q, strategy)

def test_choose_weighted_quota(tmp_path):
    r = _router(tmp_path)
    assert r.choose(["claude", "echo"]) == "echo"  # more remaining

def test_unknown_strategy_raises(tmp_path):
    with pytest.raises(ValueError):
        _router(tmp_path, strategy="nope")

def test_require_cli_filters_to_echo(tmp_path):
    r = _router(tmp_path)
    # a vendor whose CLI almost certainly isn't installed in CI is filtered out
    assert r.choose(["definitely-not-installed", "echo"], require_cli=True) == "echo"

def test_empty_candidates_raises(tmp_path):
    r = _router(tmp_path)
    with pytest.raises(ValueError):
        r.choose([], require_cli=True)

def test_vendor_available_resolves_by_binary_not_name(monkeypatch):
    # The bug: availability was checked against the vendor *name*; antigravity's binary is `agy`.
    import jailbird.adapters.base as base
    from jailbird.adapters import vendor_available, get_adapter
    assert get_adapter("antigravity").binary == "agy"
    monkeypatch.setattr(base.shutil, "which", lambda n: "/usr/bin/x" if n == "agy" else None)
    assert vendor_available("antigravity") is True          # found via `agy`, not `antigravity`
    monkeypatch.setattr(base.shutil, "which", lambda n: None)
    assert vendor_available("antigravity") is False         # `agy` absent -> unavailable
    assert vendor_available("echo") is True                 # no external binary
    assert vendor_available("not-a-vendor") is False        # unknown vendor

def test_require_cli_uses_binary_for_antigravity(tmp_path, monkeypatch):
    import jailbird.adapters.base as base
    monkeypatch.setattr(base.shutil, "which", lambda n: None)  # no real CLIs on PATH
    r = _router(tmp_path)
    # antigravity (binary `agy`) is absent -> filtered out, echo (no binary) survives
    assert r.choose(["antigravity", "echo"], require_cli=True) == "echo"
