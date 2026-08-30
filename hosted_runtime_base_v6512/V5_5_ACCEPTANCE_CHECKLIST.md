# ScoreMax V5.5 — Browser & Acceptance Checklist

## A. Baseline and migration

- [ ] Keep V5.4.2 untouched.
- [ ] Run migration dry-run against a copy of the real database.
- [ ] Confirm SQLite integrity `ok` and entity counts preserved.
- [ ] Run real migration with backup.
- [ ] Confirm legacy papers show `LEGACY_UNPINNED` where appropriate.

## B. Blueprint governance

- [ ] Admin can import the sample JSON.
- [ ] Validation shows passed checks, warnings and blockers.
- [ ] Invalid count total is blocked.
- [ ] Invalid percentage total is blocked.
- [ ] Duplicate subject is blocked.
- [ ] Same ID/version with changed checksum is rejected.
- [ ] Non-admin cannot access import/activation URLs.
- [ ] Activation requires explicit POST/CSRF and reason.
- [ ] Audit/sync history appears.
- [ ] Immutable snapshot exports correctly.

## C. Authentic mock

- [ ] With sufficient governed bank, mock contains exact 81/45/36/9/9.
- [ ] Paper is visibly labelled authentic and shows blueprint/version.
- [ ] Removing two required English items blocks release rather than substituting Biology.
- [ ] Student Access ceiling remains enforced.
- [ ] Result retains blueprint and policy version.

## D. Historical integrity

- [ ] Activate a second blueprint version.
- [ ] Old mock still shows old version/composition.
- [ ] Old result is unchanged.
- [ ] New mock uses the new version.
- [ ] Impact preview identifies changed counts/weights and bank effect.

## E. Practice purpose separation

- [ ] Proportional practice is labelled non-authentic.
- [ ] Diagnostic practice can deviate and explains adjusted allocation.
- [ ] Subject/chapter tests do not force full-exam proportions.
- [ ] No incomplete practice is presented as authentic mock.

## F. Study Plan

- [ ] Active blueprint appears in plan context.
- [ ] High-weight subject receives appropriate priority when weak.
- [ ] Critically weak low-weight subject can outrank stable high-weight subject.
- [ ] Recommendation gives understandable weight + learner-need reason.
- [ ] Evidence write-back/recovery loop from V5.4.2 still works.

## G. Projection and dashboards

- [ ] Student sees official counts/weight, projected range, confidence and next priority.
- [ ] Parent sees evidence-based blueprint contribution.
- [ ] Teacher sees class blueprint summary.
- [ ] Sparse evidence produces Low confidence rather than false precision.
- [ ] Projection snapshot is pinned and change-from-previous works after a later save.

## H. Bank sufficiency / Power House request

- [ ] Bank page shows required per mock, usable items, families and safe parallel depth.
- [ ] Thin low-weight subject is flagged.
- [ ] Draft/inactive/unapproved-family/unready items do not count.
- [ ] Content Requirement Request exports valid JSON with checksum.

## I. Rigor and mastery policy

- [ ] Slider draft does not alter the active blueprint.
- [ ] Preview shows proposed item mix and historical-form estimates.
- [ ] Sparse history is labelled low confidence.
- [ ] Activation is audited.
- [ ] New test/mastery form pins the active policy version.
- [ ] Higher rigor changes future mix/evidence, not stored question labels.
- [ ] Material tightening moves existing relevant mastery to Verification Due, not downgrade.
- [ ] Old attempts/results remain unchanged.

## J. Question import

- [ ] V5.5 workbook imports.
- [ ] Missing Family ID fails validation.
- [ ] Missing Difficulty fails validation.
- [ ] `Status=Approved` still imports Draft + inactive.
- [ ] Level and Difficulty remain separate.

## K. V5.4.2 regressions

- [ ] Login/register/reset/session invalidation.
- [ ] Practice, mastery and Study Plan.
- [ ] Teacher class/assignment workflow.
- [ ] Parent linking/revocation.
- [ ] Exam Centre access ceiling.
- [ ] Question + family publication gate.
- [ ] CSRF-protected state changes.

## L. Mobile

- [ ] Student dashboard on Android-sized viewport.
- [ ] Blueprint card readable without horizontal overflow.
- [ ] Practice buttons and mock warnings understandable.
- [ ] Admin tables usable on desktop and tolerable on tablet.
