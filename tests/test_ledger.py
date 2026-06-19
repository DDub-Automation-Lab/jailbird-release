from jailbird.router.ledger import Ledger

def test_record_and_totals(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    led.record("claude", est_cost=0.04, input_tok=100)
    led.record("claude", est_cost=0.02)
    led.record("codex", est_cost=0.01)
    t = led.totals()
    assert t["claude"].requests == 2
    assert abs(t["claude"].est_cost - 0.06) < 1e-9
    assert t["codex"].requests == 1

def test_totals_empty_when_missing(tmp_path):
    assert Ledger(str(tmp_path / "none.jsonl")).totals() == {}
