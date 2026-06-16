# TML-4PM Runtime Rollout

## Rule

T4H001 is the reference runtime. TML-4PM repositories are deployment targets.

Do not copy assumptions. Copy the runtime contract and require receipts.

## Target sequence

1. Install environment check in one low-risk TML-4PM repository.
2. Run it manually.
3. Confirm runner allocation, repository write, and artifact upload.
4. Install runtime files only after the environment check is green.
5. Run Runtime Receipt Proof.
6. Run Runtime Replay Check.
7. Run Runtime Recovery Check.
8. Promote the repository only after receipts are observed.
9. Expand from one repository to five, then to the rest of the group.

## Status labels

- REAL: current receipt exists.
- PARTIAL: code exists but execution receipt is missing.
- BLOCKED: permissions, billing, Actions, or connector prevents execution.
- ASPIRATIONAL: planned but not installed.

## TML-4PM first target

Use a low-risk repository first. Do not start with a production-critical repo.

## Promotion criteria

A TML-4PM repo is promoted only when these are true:

- environment check green
- runtime proof green
- replay green
- recovery green
- receipt artifact present
- ledger append confirmed
- no unplanned manual intervention
