# Independent Review Brief — ScoreMax V6.2

Review the actual ZIP, not this summary.

## Highest-risk areas

1. Atomic import transaction and backup ordering.
2. Rollback gates after evidence or academic review.
3. Original-file path traversal and checksum verification.
4. Prompt-pack checksum and immutable version conflict handling.
5. Candidate output isolation from live content.
6. Demo quarantine and possible orphaned rows.
7. Knowledge Hub publication/rights controls.
8. Production storage configuration.
9. CSRF/authentication on every new mutation.
10. Regression against V5.5/V6/V6.1.

## Required challenges

- Attempt a duplicate ID inside one file and against the existing bank.
- Force a runtime failure in the middle of import and verify zero questions commit.
- Attempt rollback after adding a question to an attempt, paper and academic review.
- Tamper with a stored source file before download.
- Reuse a prompt-pack ID/version with different content.
- Try to publish Growth Engine content without human action.
- Verify demo cleanup cannot affect non-demo users/content.

## Evidence supplied

- `smoke_tests_v6_2.py`
- inherited V5.5/V6/V6.1 smoke suites
- migration utility and dry-run report
- acceptance checklist
- Power House and Growth Engine contracts
