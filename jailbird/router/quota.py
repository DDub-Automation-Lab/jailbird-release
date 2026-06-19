from __future__ import annotations
from abc import ABC, abstractmethod
from jailbird.router.ledger import Ledger

class QuotaSource(ABC):
    @abstractmethod
    def remaining(self, vendor: str) -> float | None: ...

class BudgetCapQuota(QuotaSource):
    """Default offline quota: per-vendor configured cap minus ledger spend.

    The honest version of 'even-credit exhaustion'. Swap in a real vendor probe
    by implementing QuotaSource.remaining without touching the strategies.
    """
    def __init__(self, caps: dict[str, float], ledger: Ledger):
        self.caps = caps
        self.ledger = ledger

    def remaining(self, vendor: str) -> float | None:
        cap = self.caps.get(vendor)
        if cap is None:
            return None
        spent = self.ledger.totals().get(vendor)
        return cap - (spent.est_cost if spent else 0.0)
