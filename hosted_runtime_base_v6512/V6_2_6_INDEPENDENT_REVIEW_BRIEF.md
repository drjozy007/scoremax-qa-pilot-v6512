# Independent Review Brief — ScoreMax V6.2.6

Review the extracted release, not only the source folder used to build it.

## Highest-risk challenges

1. Prove a sandbox candidate cannot appear in any student-facing question pool.
2. Prove a lab run cannot create a live attempt, mastery record or Study Plan mutation.
3. Import 322 candidates and verify count, checksum, relationships and unresolved warnings.
4. Force a failure after the batch row is created but before all candidate rows insert; prove rollback.
5. Retry after failure and prove exactly one clean import.
6. Submit the same exact corpus twice and prove duplicate protection.
7. Submit the same external question/version with materially changed content in a different batch and identify the reconciliation risk.
8. Challenge every scoring family with correct, incorrect, malformed and partial responses.
9. Confirm a constructed response without a rubric/manual score receives no automatic full evidence.
10. Confirm variants/scaffolds and shared-stimulus pairs are identity-capped.
11. Confirm a Foundation-ceiling item cannot independently prove Distinction.
12. Replay all seven profiles and inspect the rationale, not only the final label.
13. Confirm repeated variants do not produce verified mastery.
14. Confirm Verification Due is separate from downgrade.
15. Confirm failed delayed reconfirmation creates recovery rather than silent deletion of prior state.
16. Create a collision with a live question ID and confirm Gate 4 blocks acceptance.
17. Corrupt or remove a relationship target and confirm the warning is retained.
18. Attempt all admin routes as student, teacher and parent.
19. Inspect exported run JSON for complete scoring, evidence, state and recovery lineage.
20. Run the full inherited regression stack and migration rehearsal.

## Required verdict format

Classify each capability as:

- Verified Safe for QA Sandbox
- Implemented but Weakly Tested
- UI Complete Only
- Pilot Restricted
- Release Blocker
- Deferred

Do not describe V6.2.6 as approving the candidate corpus. It only provides a governed technical laboratory.
