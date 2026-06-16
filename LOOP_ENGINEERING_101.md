# Loop Engineering 101

## Purpose

This repository is the clean-room runtime lane for proving loop engineering outside the failing legacy account/org environment.

Canonical loop:

`Signal -> Task -> Execution -> Check -> Evidence -> Receipt -> Ledger -> Rule -> Next Run`

## Reality rules

- No receipt means not REAL.
- Runtime evidence beats memory.
- A workflow must execute, emit evidence, and produce a receipt before work is classified REAL.
- Failures must be retried, rerouted, rolled back, or explicitly marked BLOCKED.
- Old-account failures must not be allowed to contaminate this clean lane.

## Initial proof already observed

- Fresh T4H001 repo created.
- GitHub Actions parsed a minimal workflow.
- Runner executed successfully in 11 seconds.
- The prior "no steps" failure mode did not reproduce.

## Next proof ladder

1. Minimal echo workflow.
2. Checkout and list repository files.
3. Generate local runtime receipt.
4. Upload receipt artifact.
5. Run loop runner.
6. Validate receipt schema.
7. Promote only after repeated successful receipts.
