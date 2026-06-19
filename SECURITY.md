# Security & secret-leak prevention

This repo is public. The entire commit history is published, not just the current files, so we
guard against secrets / personal data reaching the remote in **five layers** (defense in depth —
a deny-hook for the repository itself).

## Enable the local guards (once, after cloning)

```bash
bash scripts/install-hooks.sh     # sets core.hooksPath -> .githooks
```

## The layers

1. **`.gitignore`** ignores vendor config written by `jailbird apply` (`.claude/`, `.codex/`,
   `.gemini/`), ledgers/logs, and secret material (`.env`, `*.key`, `*.pem`, …).
2. **pre-commit hook** (`.githooks/pre-commit`) blocks a commit whose staged content matches a
   secret pattern (`sk-…`, `gh[pousr]_…`, `AKIA…`, `AIza…`, private keys, `Bearer …`) or a
   personal-coupling token.
3. **pre-push hook** (`.githooks/pre-push`) — the gate before anything goes public: scans the
   commits being pushed for secrets/PII, requires every pushed commit to use a GitHub **noreply**
   author email, and runs the personal-coupling scrub test. Blocks the push on any failure.
4. **CI** (`.github/workflows/secret-scan.yml`) runs **gitleaks** over full history plus this
   repo's own scanner on every push/PR. GitHub's native secret scanning is also on for public repos.
5. **Pre-publish check** (`scripts/pre-publish-check.sh`) — run once before the first push:
   full-history scan, working-tree scan, author-email check, scrub test, and a tracked-file review.

## Operational rule

Run live testing against real vendors in a **throwaway directory**, never the repo:

```bash
jailbird apply --vendor claude --base "$(mktemp -d)"
jailbird run   --vendor claude --prompt "…" --ledger "$(mktemp -d)/ledger.jsonl"
```

so provisioned config and ledgers never land in the working tree.

## Reporting

Found a leaked credential in history? Treat it as compromised — rotate the credential first, then
scrub history (`git filter-repo`) or re-publish from a squashed history.
