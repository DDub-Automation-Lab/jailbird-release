from __future__ import annotations
from collections.abc import Callable
from jailbird.router.ledger import Ledger
from jailbird.router.quota import QuotaSource

def round_robin(vendors: list[str], ledger: Ledger, quota: QuotaSource, kind: str | None) -> str:
    t = ledger.totals()
    return min(vendors, key=lambda v: t[v].requests if v in t else 0)

def least_used(vendors: list[str], ledger: Ledger, quota: QuotaSource, kind: str | None) -> str:
    t = ledger.totals()
    return min(vendors, key=lambda v: t[v].est_cost if v in t else 0.0)

def weighted_quota(vendors: list[str], ledger: Ledger, quota: QuotaSource, kind: str | None) -> str:
    rems = {v: quota.remaining(v) for v in vendors}
    if all(r is None for r in rems.values()):
        return least_used(vendors, ledger, quota, kind)
    def rem(v: str) -> float:
        r = rems[v]
        return r if r is not None else float("inf")
    return max(vendors, key=rem)

_BEST_FIT = {"design": "claude", "review": "claude", "qa": "antigravity",
             "long_context": "antigravity", "implement": "codex", "bulk_edit": "codex"}

def best_fit(vendors: list[str], ledger: Ledger, quota: QuotaSource, kind: str | None) -> str:
    pref = _BEST_FIT.get(kind or "")
    if pref in vendors:
        return pref
    return least_used(vendors, ledger, quota, kind)

STRATEGIES: dict[str, Callable[..., str]] = {
    "round_robin": round_robin, "least_used": least_used,
    "weighted_quota": weighted_quota, "best_fit": best_fit,
}
