# ScoreMax V6.4.0 — Live-Pilot Defect Register

This is the single launch register for the V6.4 candidate. P0/P1 items confirmed during build were fixed systemically before sealing. P2 items do not reopen the accepted core unless trivial and isolated.

| ID | Severity | Area | Decision | Status |
|---|---|---|---|---|
| SM640-001 | P1 | Student programme context disappeared after FSc 1 selection | Persistent global FSc 1/FSc 2/MDCAT context | **FIXED** |
| SM640-002 | P1 | Home hero wasted space / did not show learner mastery identity | Context-aware mastery hero + Starting Point state | **FIXED** |
| SM640-003 | P1 | Login identity unclear after generated ScoreMax ID | Explicit email or ScoreMax ID language | **FIXED** |
| SM640-004 | P1 | Teacher referral model lacked teacher→teacher override/reporting | Extend existing referral ledger; one-level override only | **FIXED** |
| SM640-005 | P1 | No explicit governed direct-intake contingency when Power House transport fails | Reuse importer as Emergency Direct Intake, max 3,000 | **FIXED** |
| SM640-006 | P0 | Emergency release could leave family gate closed | Release eligible family + question together | **FIXED** |
| SM640-007 | P0 | R2-required emergency row could be under-specified by release fence | Explicit R2/dual-review block | **FIXED** |
| SM640-008 | P1 | Emergency source row lineage loss risk | Preserve worksheet + row | **FIXED** |
| SM640-009 | P1 | 3,000 release parameter-limit risk | Chunk release writes | **FIXED** |
| SM640-010 | P1 | Paid teacher attribution lost when rate=0/unconfigured | Preserve ledger as `rate_not_configured` | **FIXED** |
| SM640-011 | P1 | Referral export formula-injection risk | Excel-safe text export | **FIXED** |
| SM640-012 | P2 | Corrupt restore showed traceback | Clean integrity failure handling | **FIXED** |
| SM640-013 | Gate | Live domain/HTTPS/production process | Qualify exact sealed build on host | **PENDING** |
| SM640-014 | Gate | Browser/mobile/accessibility founder acceptance | Real Edge/Chrome/mobile/keyboard/200% zoom | **PENDING** |
| SM640-015 | Gate | Real Power House approved-content bridge | Prove lossless end-to-end chapter | **PENDING** |
