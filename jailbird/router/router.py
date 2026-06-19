from __future__ import annotations
from jailbird.adapters import vendor_available
from jailbird.router.ledger import Ledger
from jailbird.router.quota import QuotaSource
from jailbird.router.strategies import STRATEGIES

class Router:
    def __init__(self, ledger: Ledger, quota: QuotaSource, strategy: str = "weighted_quota"):
        if strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy '{strategy}'. known: {sorted(STRATEGIES)}")
        self.ledger = ledger
        self.quota = quota
        self.strategy = strategy

    def choose(self, vendors: list[str], *, kind: str | None = None,
               require_cli: bool = False) -> str:
        candidates = [v for v in vendors
                      if not require_cli or vendor_available(v)]
        if not candidates:
            raise ValueError("no available vendors after filtering")
        return STRATEGIES[self.strategy](candidates, self.ledger, self.quota, kind)
