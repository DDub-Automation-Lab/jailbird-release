from jailbird.router.ledger import Ledger
from jailbird.router.quota import BudgetCapQuota
from jailbird.router.strategies import round_robin, least_used, weighted_quota, best_fit, STRATEGIES

def _setup(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record("claude", est_cost=5.0)   # heavily used
    led.record("codex", est_cost=1.0)
    q = BudgetCapQuota({"claude": 10.0, "codex": 10.0, "antigravity": 10.0}, led)
    return led, q

def test_least_used_picks_cheapest(tmp_path):
    led, q = _setup(tmp_path)
    assert least_used(["claude", "codex"], led, q, None) == "codex"

def test_weighted_quota_picks_most_remaining(tmp_path):
    led, q = _setup(tmp_path)  # antigravity unused -> 10 remaining, most
    assert weighted_quota(["claude", "codex", "antigravity"], led, q, None) == "antigravity"

def test_round_robin_picks_fewest_requests(tmp_path):
    led, q = _setup(tmp_path)
    assert round_robin(["claude", "codex", "antigravity"], led, q, None) == "antigravity"

def test_best_fit_uses_kind_then_falls_back(tmp_path):
    led, q = _setup(tmp_path)
    assert best_fit(["claude", "codex"], led, q, "implement") == "codex"
    assert best_fit(["claude", "codex"], led, q, "unknown") == "codex"  # falls back to least_used
    assert STRATEGIES["weighted_quota"] is weighted_quota


def test_weighted_quota_ties_break_by_least_used(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record("claude", est_cost=5.0)
    led.record("codex", est_cost=1.0)
    q = BudgetCapQuota({}, led)
    assert weighted_quota(["claude", "codex"], led, q, None) == "codex"
