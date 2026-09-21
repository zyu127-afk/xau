# Release criteria

A repository commit is not a production release until all of these are true:

- Python core CI passes.
- ATAS bridge core CI passes.
- Guardian compiles in the user's installed MetaEditor with zero errors.
- Demo-account market open/close/modify flows pass for both logical slots.
- Netting and/or hedging mode used by the target broker is explicitly validated.
- Every live test position shows a real server-side SL.
- Engine kill, AI outage and ATAS outage do not remove protection from existing MT5 positions.
- Friday/session-end protection is observed on the actual broker server clock/session metadata.
- ATAS live contract switch emits instrument-change and forces mapping warm-up.
- GC↔MT5 mapping reaches configured quality thresholds before order-flow-dependent entries are enabled.
- Backup/restore and new-PC migration complete without exposing `secrets.local`.

Until then the build must be treated as development/demo-only.
