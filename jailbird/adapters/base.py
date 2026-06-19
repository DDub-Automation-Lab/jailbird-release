from __future__ import annotations
import shutil
from abc import ABC, abstractmethod
from jailbird.types import Task, Event, ToolCall, ConfigArtifact
from jailbird.policy import Policy

class VendorAdapter(ABC):
    name: str = ""
    # External CLI executable this adapter shells out to. "" means no external binary is
    # required (always available — e.g. the echo mock runs in-process). Vendors whose binary
    # differs from their registry name MUST set it (e.g. antigravity -> "agy").
    binary: str = ""
    config_home_env: str | None = None

    @abstractmethod
    def build_argv(self, task: Task, *, autonomy: str, config_dir: str) -> list[str]: ...
    @abstractmethod
    def governance_artifacts(self, policy: Policy, scope: str) -> list[ConfigArtifact]: ...
    @abstractmethod
    def parse_stream(self, line: str) -> Event | None: ...
    @abstractmethod
    def parse_hook_input(self, d: dict) -> ToolCall: ...
    @abstractmethod
    def deny_response(self, reason: str) -> str: ...

    def allow_response(self) -> str:
        return ""  # empty stdout = "no decision, normal evaluation proceeds"

    def is_available(self) -> bool:
        """Whether this vendor can actually run here: True if it needs no external
        binary (echo), else whether its ``binary`` is on PATH. Resolves by the adapter's
        real binary, not its registry name (antigravity's binary is ``agy``)."""
        return not self.binary or shutil.which(self.binary) is not None

    def harness_env(self, config_dir: str) -> dict[str, str]:
        """Env vars that point this vendor's CLI at the harness-owned config home
        (and preserve auth). Default: none — the vendor takes config via build_argv
        flags (e.g. Claude's ``--settings``) instead of a config-home env var."""
        return {}
