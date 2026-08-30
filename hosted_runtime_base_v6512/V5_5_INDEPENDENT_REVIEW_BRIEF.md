# ScoreMax V5.5 Independent Review Brief

Review the source as evidence; do not accept the build report at face value.

## Priority questions

1. Can an imported blueprint be changed without a new version/checksum?
2. Can a non-admin import, activate, supersede or archive a blueprint/policy?
3. Can a structurally incomplete mock be labelled authentic?
4. Does an authentic mock always use exact section counts and retain its immutable snapshot?
5. Can activating a new blueprint rewrite old papers/results/projections?
6. Do sessions/attempts truly pin both blueprint and assembly-policy versions?
7. Can diagnostic/proportional practice be confused with authentic mocks?
8. Does bank sufficiency exclude Draft, inactive, unapproved-family, unready or rights-blocked questions?
9. Can a rigor/mastery slider relabel question metadata or retroactively downgrade mastery?
10. Does material policy tightening correctly produce Verification Due?
11. Does the historical simulation clearly distinguish internal historical re-evaluation from external-percentile calibration?
12. Can official exam weight incorrectly redefine mastery or dominate severe learner need?
13. Are Level and Difficulty genuinely independent in import and selection?
14. Does V5.4.2→V5.5 migration preserve all existing data and mark legacy papers honestly?
15. Are there new authorization, CSRF, IDOR, SQL injection, file-upload or JSON resource-exhaustion risks?

## Specific regression targets

Re-run V5.4.2 integrity checks covering mastery reconfirmation, dual question/family publication, Exam Centre access ceiling, password-reset/session invalidation, teacher assignment membership/availability and CSRF.

## Scope boundaries

Do not demand PostgreSQL, IRT, live Power House API, job queues or a monolithic-app refactor as a condition for assessing whether V5.5 correctly implements its stated blueprint layer. Those are separate planned phases.
