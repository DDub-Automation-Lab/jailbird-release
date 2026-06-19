from __future__ import annotations
from jailbird.adapters import get_adapter
from jailbird.policy import Policy
from jailbird.types import ConfigArtifact

def compile_policy(policy: Policy, vendors: list[str], scope: str
                   ) -> dict[str, list[ConfigArtifact]]:
    return {v: get_adapter(v).governance_artifacts(policy, scope) for v in vendors}
