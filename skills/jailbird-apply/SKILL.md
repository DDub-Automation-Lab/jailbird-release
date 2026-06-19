---
name: jailbird-apply
description: Provision jailbird governance config (deny-hook + native rules) into place for a coding-agent vendor. Use when an agent should self-install or refresh its tool/command/path deny-list for Claude, Codex, or Antigravity. Triggers include "apply jailbird governance", "install the deny-hook", "provision governance config".
---

# jailbird-apply

Push a config-driven deny-list into a vendor's native governance surface — one command, any
vendor.

## Use

```bash
jailbird apply --policy jailbird.policy.yaml --vendors claude codex antigravity --scope project
```

- `--scope project` (default) writes repo-local `.claude` / `.codex` / `.agents` config (agent-writable).
- `--scope user` writes `~/.claude` / `~/.codex` (Antigravity hooks are project-local `.agents/`).
- `--scope system` targets the tamper-resistant managed tier (needs elevated install).
- `--check` reports drift without writing.
- `--remove` removes previously written config.
- `--dry-run` previews what would be written without touching disk.

Only `--scope system` is tamper-resistant; project/user tiers are advisory self-governance.

See [docs/CAPABILITY-MATRIX.md](../../docs/CAPABILITY-MATRIX.md) for what each layer actually
guarantees.
