# ScoreMax V6.5.0 Changelog

## Integration contract implementation

1. Added `scoremax_integration_v1.py` as the governed ScoreMax-side adapter for frozen contract v1.
2. Added immutable inbound message, receipt, quarantine, Power House release/question/stimulus/blueprint and outbound attempt/outbox persistence.
3. Added authenticated inbound endpoints:
   - `POST /api/integration/v1/power-house/content-releases`
   - `POST /api/integration/v1/power-house/assessment-blueprints`
   - `GET /api/integration/v1/health`
4. Added exact Power House question/release version pins to learner session and attempt evidence.
5. Added outbound `SM_PH_DELIVERY_EVIDENCE_V1`, `SM_PH_CONTENT_REQUIREMENT_V1` and `SM_GE_PRODUCT_EVENT_V1` production.
6. Extended existing referral/payment events without moving payment or reward authority out of ScoreMax.
7. Added retry/backoff, receipt recording, dispatch attempts, idempotency and quarantine.
8. Added current/previous credential pairs for controlled service-secret rotation and HMAC replay protection.
9. Extended the existing admin surface with integration health; no fourth control platform was created.
10. Added V6.5 launch, backup/restore, dispatcher and acceptance tools.

## Preserved unchanged in architecture

- Student UX and programme switching.
- Existing/Potential Mastery presentation.
- Universal Mastery pilot/shadow controls.
- Study Plan, Progress and Exam flows.
- Teacher referral one-upstream rule and payment ledger authority.
- Emergency Direct Intake (3,000 rows).
- Power House reviewer authority boundary.
