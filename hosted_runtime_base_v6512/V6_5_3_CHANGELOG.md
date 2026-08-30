# ScoreMax V6.5.3 Changelog

## Integration admission rectification
V6.5.3 closes the governed V6.5.2 rejection class systemically across semantic admission, immutable evidence, canonical identity, transport/receipt handling, queue operations and active blueprint execution.

### Academic and learner-delivery integrity
- Added zero-side-effect semantic validation for supported delivery type, option uniqueness, key membership/cardinality, numerical answer/tolerance, marking coherence, single-version snapshots and stimulus references.
- Preserved complete immutable stimulus evidence while projecting only learner-safe stimulus content.
- Added execution fidelity for numeric/tolerance, multiple select, text, boolean, partial/fractional and negative marks.
- Rubric-only content that lacks a supported governed delivery route is explicitly rejected rather than silently admitted inertly.

### Identity and evidence
- Added ScoreMax-owned semantic checksums for content releases and blueprints.
- Exact idempotent replay returns the original durable receipt.
- Same ID/version with changed semantics is quarantined even when caller-supplied checksums are unchanged.
- Delivery evidence now derives from immutable session/answer scope pins, not current mutable question location.

### Transport and operations
- HTTPS is enforced before credential access or request construction.
- Receipt receiver/message/checksum binding is enforced across 200/202/409/422/429/503 handling.
- Added atomic claim leases, fair contract interleaving, worker heartbeat, backlog-by-source/status visibility and audited requeue.
- Added hosted worker Procfile entry and Windows worker/start/backup/restore/acceptance scripts.

### Blueprint runtime
- RELEASED Power House blueprints now extend the existing ScoreMax blueprint runtime and control future permitted inventory, assembly distributions, timing and marking through immutable session pins.

No student UX redesign or Power House reviewer-workflow reconstruction is included.

### Upgrade safety from rejected V6.5.2 state
- Added one-time semantic reconciliation for legacy integration rows during schema upgrade.
- Legacy content without V6.5.3 semantic identity is reconstructed from immutable stores, revalidated and learner-safely reprojected; unsafe legacy content is quarantined and removed from active learner inventory rather than inherited silently.
- Legacy `IMMUTABLE_ONLY` blueprints are revalidated and projected into the existing ScoreMax runtime when supported; otherwise they are migration-quarantined.
