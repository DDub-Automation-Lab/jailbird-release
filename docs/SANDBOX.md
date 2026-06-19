# The bypass-proof layer: OS / container sandbox

The config + hook layers are strong but app-enforced. The only layer an agent cannot reconfigure
from inside its own tool calls is an OS/container sandbox the harness owns. Recommended recipe:

```bash
docker run --rm -it \
  --network none \
  --read-only -v "$PWD":/work:ro \
  --tmpfs /work/.scratch \
  -w /work \
  your-agent-image jailbird run --vendor codex --prompt "..."
```

- `--network none` stops any push/exfil by capability — kills `git push` and remote writes
  regardless of how the command is spelled.
- `--read-only` + volume mount stops destructive writes outside the scratch dir.

This holds even if a vendor's in-process controls are bypassed, because it lives outside the
agent process. v1 documents this recipe; container orchestration is deliberately out of scope.

See [CAPABILITY-MATRIX.md](CAPABILITY-MATRIX.md) for the full layer comparison.
