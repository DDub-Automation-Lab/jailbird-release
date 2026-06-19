from jailbird.router.ledger import Ledger
from jailbird.router.quota import BudgetCapQuota

def test_remaining_subtracts_spend(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record("claude", est_cost=3.0)
    q = BudgetCapQuota({"claude": 10.0}, led)
    assert q.remaining("claude") == 7.0

def test_no_cap_returns_none(tmp_path):
    q = BudgetCapQuota({}, Ledger(str(tmp_path / "l.jsonl")))
    assert q.remaining("codex") is None
