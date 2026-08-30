# ScoreMax V6.5.1 Rectification Defect Register

| ID | Prior severity | Defect | V6.5.1 decision | Evidence |
|---|---|---|---|---|
| SM651-001 | P0 | No strict JSON Schema gateway; invalid content could reach inventory | RECTIFIED | strict Draft 2020-12 gateway; supplied adversarial case NOT_CONFIRMED |
| SM651-002 | P0 | PH opaque ID collision could overwrite legacy ScoreMax question | RECTIFIED | PH projection namespace + owner guard; adversarial collision NOT_CONFIRMED |
| SM651-003 | P0 | Question version conflated with release membership | RECTIFIED | independent version store/membership; 0/50/90/100% unchanged releases PASS |
| SM651-004 | P0 | Outbound C/D/E messages could violate frozen schemas | RECTIFIED | strict validation before outbox insert; generated envelopes PASS |
| SM651-005 | P0 | HTTP 200/202 treated as delivered without validated receipt | RECTIFIED | ACCEPTED/DUPLICATE only; malformed/wrong/rejected/quarantined cases durable PASS |
| SM651-006 | P1 | NOT_REQUIRED source check/optional clearance/null effective_at mishandled | RECTIFIED | schema-valid compatibility tests PASS |
| SM651-007 | P1 | Strict blueprint gateway missing | RECTIFIED | invalid empty sections rejected 422 before projection |
| SM651-008 | P1 | Unanswered counted incorrect | RECTIFIED | telemetry shows skipped_count, incorrect_count 0 |
| SM651-009 | P1 | Non-HTTPS/weak secret strict preflight allowed | RECTIFIED | strict preflight BLOCKED |
| SM651-010 | P1 | Referral lineage ID unstable | RECTIFIED | canonical attribution ID stable across event chain |
| SM651-011 | P1 | Learner request path ran full historical projections | RECTIFIED | incremental queue + background dispatch; request path static check PASS |
| SM651-012 | P1 | Additive V6.5.0 DB migration assumed new release columns | FOUND DURING RECTIFICATION; RECTIFIED | exact parent DB upgrade replay PASS after ensure-column architecture fix |

Integration Control supplied adversarial harness final result: **18/18 NOT_CONFIRMED; confirmed_defects=0**.
