# ScoreMax V6.5.7 Changelog

## Exact parent

Frozen ScoreMax V6.5.6 ZIP SHA-256:

`64244e5d64d5df2bbeb262b0554b3c5e0b69b3f31378e8c338c71e5fb378cdb2`

## Rectified finding

`INT-PHSM-B01-P0-002 — ScoreMax auto-activates accepted Power House content when effective_at is null/due.`

## Narrow changes

- Power House content admission stops at `STAGED`; admission never grants learner activation authority.
- Added one additive `integration_ph_product_activation_authorizations` table for exact release/version/package-checksum authorization evidence.
- Added `authorize_product_activation(...)` requiring exact identity, actor and reason.
- Hardened `_activate_release(...)` so even internal callers cannot activate without matching authorization evidence.
- Recast `activate_due_releases()` as crash recovery for already-authorized staged releases only; Power House `effective_at` remains metadata.
- Extended the existing Integration Health admin page with the minimal ScoreMax activation action and evidence display.
- Updated active descendant tests/helpers so tests that require learner projection explicitly authorize the staged release first.
- Added permanent V6.5.7 product-activation attacks and updated 300/1,500 canonical integration scale to prove staged-before-activation behavior.

## Intentionally untouched

Learner/mastery logic, reviewer architecture, payments, referrals, Emergency Intake, blueprint behavior, manifest-origin security, explicit-port security and already-cleared integration semantics remain unchanged.
