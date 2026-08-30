# ScoreMax V6.5.0 Known Limitations / Pending Cross-System Gates

These are not silently treated as passed.

1. **Real Power House vertical slice not yet proven.** The ScoreMax adapter passes canonical frozen-contract fixtures and synthetic 300/1,500 packages, but one real academically approved Power House chapter must still traverse the actual Power House exporter -> ScoreMax -> learner evidence chain without manual repair.
2. **Counterpart builds/receipts pending.** Power House and Growth Engine must implement and return their sides before outbound ScoreMax events can be qualified end-to-end.
3. **Frozen v1 `MANIFEST_PULL` schema contradiction.** The frozen PH content schema permits `MANIFEST_PULL` but also requires inline `questions` with `minItems: 1`, so ScoreMax does not silently redefine the contract. V6.5 rejects `MANIFEST_PULL` with `FROZEN_MANIFEST_PULL_SCHEMA_CONFLICT` and supports `INLINE` until Integration Control versions a rectification.
4. **Blueprint projection is fail-safe.** A Power House blueprint is stored immutably; if the legacy ScoreMax framework identity required for deterministic projection is absent, it remains `IMMUTABLE_ONLY` rather than inventing an identity.
5. **Hosted production qualification pending.** Domain/TLS, managed persistence/database architecture, SMTP, browser/mobile/keyboard/200% zoom and hosted service-secret qualification remain Production Reality Audit gates.
6. **Separate adversarial audit pending.** The frozen V6.5 candidate must be attacked independently without editing during that stage.
7. **Universal Mastery governed mappings remain an academic-content dependency.** ScoreMax does not invent Knowledge Node / Claim Family / Seed mappings for legacy content.
