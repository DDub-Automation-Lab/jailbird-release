from __future__ import annotations
import json
import tomllib
import tomli_w

def deep_merge(base: dict, new: dict) -> dict:
    out = dict(base)
    for k, v in new.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        elif isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = out[k] + [x for x in v if x not in out[k]]
        else:
            out[k] = v
    return out

def load_structured(text: str, fmt: str) -> dict:
    if not text.strip():
        return {}
    return json.loads(text) if fmt == "json" else tomllib.loads(text)

def dump_structured(data: dict, fmt: str) -> str:
    return json.dumps(data, indent=2) if fmt == "json" else tomli_w.dumps(data)
