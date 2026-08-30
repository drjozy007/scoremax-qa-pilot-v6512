# ScoreMax V6.5.0 Rollback Evidence

## Frozen parent

`ScoreMax_V6_4_0_Live_Pilot_UX_Operations_Candidate.zip`

SHA-256: `25dee1e56bfb517e032387fed566e4cfb9335a74c04b47c0e18e63a4a03ef64e`

The parent package remains physically available and unchanged.

## Migration character

V6.5 integration persistence is additive: new integration tables and new nullable/defaulted Power House pin/projection columns are added. V6.5 does not destructively rewrite learner/mastery/referral records.

## Compatibility replay

A disposable database was initialized with V6.5, producing the integration tables and columns. The exact V6.4 parent was then initialized against that V6.5 database. V6.4 completed initialization and `PRAGMA integrity_check` returned `ok`; learner/user records remained readable. This demonstrates code rollback compatibility for the additive local schema in the tested SQLite path.

Production rollback still requires the live deployment's pre-migration backup plus one-action deployment rollback evidence; that remains a hosted qualification gate.
