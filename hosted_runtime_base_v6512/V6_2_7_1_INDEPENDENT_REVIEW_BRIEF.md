# Independent Review Brief — ScoreMax V6.2.7.1

Independently verify that V6.2.7.1 closes all findings in the Claude V6.2.7 audit without weakening the previously verified confidentiality, live-write or governance boundaries.

## Required adversarial reproductions

1. Call `create_assignment()` directly for round two without `parent_assignment_id` and with the first reviewer; both must fail.
2. Fire repeated timer requests faster than wall-clock time; credited time must never exceed server elapsed time.
3. Use an invitation link without the separate code; activation and password change must fail.
4. Race identical imports, first-review assignments and second-review claims using separate database connections; exactly one valid row must commit in each case.
5. Migrate a genuine V6.2.7 database containing an unused invitation; core and reviewer counts must remain preserved and the invitation must require safe reissue.
6. Confirm the production ZIP contains no generated private/test upload artifacts.

## Regression boundary

Re-run all prior suites from V5.5 through V6.2.7 and the new V6.2.7.1 suite. Inspect whether the tests genuinely exercise the corrected paths.

## Output

Return an independent Markdown report with exact commands, findings, severities, reproduction steps, verified claims, limitations and a controlled-pilot verdict. Do not modify the source during the first audit pass.
