from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
try:
    import fcntl  # POSIX only; Windows users get no cross-process lock (documented)
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

@dataclass
class Usage:
    requests: int = 0
    input_tok: int = 0
    output_tok: int = 0
    est_cost: float = 0.0

class Ledger:
    def __init__(self, path: str):
        self.path = Path(path)

    def record(self, vendor: str, *, requests: int = 1, input_tok: int = 0,
               output_tok: int = 0, est_cost: float = 0.0) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"vendor": vendor, "requests": requests, "input_tok": input_tok,
                           "output_tok": output_tok, "est_cost": est_cost})
        with open(self.path, "a") as f:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line + "\n")
            finally:
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_UN)

    def totals(self) -> dict[str, Usage]:
        out: dict[str, Usage] = {}
        if not self.path.exists():
            return out
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            u = out.setdefault(r["vendor"], Usage())
            u.requests += r.get("requests", 0)
            u.input_tok += r.get("input_tok", 0)
            u.output_tok += r.get("output_tok", 0)
            u.est_cost += r.get("est_cost", 0.0)
        return out
