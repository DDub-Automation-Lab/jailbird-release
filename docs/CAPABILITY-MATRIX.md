# Governance capability matrix

jailbird compiles one policy to each vendor's native controls and enforces in layers. Only the
OS/container sandbox is truly bypass-proof.

| Layer | What it blocks | Bypass-proof? |
|---|---|---|
| Preflight static scan (always-on) | Denied strings in the brief/argv before launch | No — advisory |
| Native deny hook (Claude / Antigravity `PreToolUse`) | Tool calls matched by the policy | Strong, app-level (shell-string matching is evadable). **Codex caveat:** `PreToolUse` hooks do **not** fire under `codex exec` (upstream [openai/codex#25875](https://github.com/openai/codex/issues/25875), [#18607](https://github.com/openai/codex/issues/18607)) — so in the non-interactive path jailbird uses, Codex's live deny is the execpolicy layer below, not the hook |
| `tools.exclude` / execpolicy `forbidden` / MCP allowlist | Named tools / hard-denied commands (Codex's effective deny under `exec` — parses the inner command out of `zsh -lc` via tree-sitter) | Strong for named tools / command prefixes |
| OS / container sandbox (`--network none`, read-only mounts) | Egress + writes by *capability* | **Yes** — kernel-enforced |

> **Apply precondition:** `jailbird run` does NOT auto-provision governance. Run `jailbird apply`
> first to install native hooks and policies (e.g. Antigravity's deny-hook only fires once `apply`
> has installed `.agents/hooks.json`).

**Rule:** the harness owns argv and never passes a flag that disables governance or the sandbox
(`--dangerously-skip-permissions`, Codex `--yolo`/`danger-full-access`, Antigravity
`--dangerously-skip-permissions`).

See [docs/SANDBOX.md](SANDBOX.md) for the bypass-proof container recipe.

## Live-validation status

Honest per-vendor status against the real CLIs (not just unit tests):

| Vendor | Stream parsing | Governance deny (live) | Mechanism |
|---|---|---|---|
| **Claude** | ✅ validated | ✅ **proven** — real `claude -p` hit the `PreToolUse` hook and was blocked with the policy reason | `PreToolUse` hook |
| **Codex** | ✅ validated (`codex exec --json`) — note: codex reports token counts, not `cost_usd`, so ledger cost reads 0 | ✅ **proven** — `jailbird run --vendor codex` blocked a denied shell command live (`blocked=True`); a benign task was not blocked (control). Reproduce with `JAILBIRD_LIVE_CODEX=1 pytest tests/test_codex_live.py` | **execpolicy `forbidden`** (from `deny_commands`), not the hook — hooks don't fire under `codex exec` |
| **Antigravity** (`agy`) | ✅ validated (`agy --print`, plain-text) — Gemini 3.x; no `cost_usd`, ledger cost reads 0 | ✅ **proven** — `jailbird run --vendor antigravity` blocked a denied shell command live (`blocked=True`); benign task not blocked (control). Reproduce with `JAILBIRD_LIVE_ANTIGRAVITY=1 pytest tests/test_antigravity_live.py` | **`PreToolUse` hook** (`.agents/hooks.json`) — fires and blocks in headless `--print`, unlike `codex exec` |

> The standalone Gemini CLI adapter was **removed** — its free tier is auth-ineligible
> (`IneligibleTierError`, migrated to the Antigravity suite). The same Gemini models are now reached,
> and governed, through `agy` (the `antigravity` vendor).

**How Antigravity governance is wired (pinned `agy` 1.0.2):** `jailbird apply --vendor antigravity --base $DIR`
writes `$DIR/.agents/hooks.json` (a `PreToolUse` command hook → `jailbird.govern.hook --vendor antigravity`).
`agy --print` runs headless against Gemini 3.x using the existing Antigravity OAuth login (no config-home
relocation needed — hooks are project-local and auth is read from `~/.gemini`). The shell tool is
`run_command`; the hook reads `toolCall.args.CommandLine` and denies via `{"decision":"deny"}`. Because
`agy` rewords the denial in its prose stdout, block detection uses a **deterministic sentinel**: the deny
hook appends to `JAILBIRD_BLOCK_SENTINEL` and the runner sets `RunResult.blocked` from it (this also hardens
Claude's block detection). Never pass `--dangerously-skip-permissions` (it disables the hook).

**How Codex governance is wired (pinned `codex` 0.137.0):** `jailbird apply --vendor codex --base $DIR`
writes `$DIR/.codex/config.toml` + `$DIR/.codex/rules/jailbird.rules`. At run time `jailbird run`
points `CODEX_HOME` at `$DIR/.codex` (so the harness config + execpolicy rules load) and symlinks the
real `auth.json` in so login is preserved. Codex parses the inner command out of its `zsh -lc` wrapper
and a `forbidden` `prefix_rule` rejects it before execution; the runner detects the rejection and sets
`RunResult.blocked`.

**Codex limitation (honest):** because `PreToolUse` hooks are inert under `codex exec`, a policy's
`deny_tools` (tool-name denial, hook-only) is **not** enforced for Codex in `exec` mode — only
`deny_commands` (→ execpolicy) is. `deny_tools` is enforced for Claude. The Codex hook config is still
provisioned (correct schema, regex matcher) so it activates automatically if/when upstream wires hooks
into `exec`.

Claude, Codex, and Antigravity governance are all proven live. The three supported vendors are
`claude`, `codex`, and `antigravity` (plus the `echo` mock for offline CI). The legacy standalone
Gemini CLI adapter has been removed — Gemini models are now reached, and governed, through `agy`.
