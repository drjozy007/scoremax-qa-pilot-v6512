# ScoreMax UK 11+ — UX-to-Engineering integration handoff (Chat 3)

**Date:** 23 November 2026  
**Owner:** Product & UX (Chat 1)  
**Target:** Existing ScoreMax platform with UK-only routing; integration owned by Chat 3.  
**UK static preview:** https://scoremax-11plus-preview.onrender.com  
**Preview deployed SHA:** `1dc6fc3aa13c6a7512716aa8119e425eea623b94`  
**Rendered status:** Render deployment reported LIVE (23 Nov, 18:42 GMT). Browser interaction not yet independently confirmed.

## Executive decision

Extend the existing authenticated ScoreMax student/parent/teacher screens and their study plans, practice, mocks, mastery, analytics and supporting services. Use the static preview for *presentation specifications* only. It is not a second learner platform. Maintain UK isolation and protect Pakistan production, existing academic contracts, data and migrations.

## Source-of-truth and environment boundaries

- **Power House:** canonical approved question/version, evidence, memberships, mappings, rights, correction/hold, academic release.
- **ScoreMax:** school selection, learner experience, delivery, response collection, native marking, mastery, plans, analytics and role-specific views.
- **UK preview:** static non-persistent visual reference using 24 calibration questions; never a qualified bank, learning record or official admissions outcome.
- **Changes allowed in this chat:** static UI markup/CSS/JS on `preview/uk11-static-site-20261123` and related UK-only presentation documentation.
- **Forbidden here:** production database writes, native scorer edits, Power House academic authorisation, Pakistan code/config changes, authentication secrets or release qualification.

## Existing implementation inspected

The current GitHub repository root includes `SCOREMAX_ONLY_UPLOAD_TO_GITHUB_V6_5_12.zip`, but the contents of that binary source archive **were not accessible for line-by-line inspection in this workstream**. Consequently, module names, routes, table fields and API endpoints in the running Pakistan application are **not verified**. Before implementation, Chat 3 must inspect and inventory the actual inherited authenticated modules and match every UI function to the closest existing screen or endpoint.

Confirmed UK preview files:
- `uk11_preview_site/index.html` — existing demo shell, routing data, 24 calibration questions, sample player, parent and school views.
- `uk11_preview_site/uk11-ux-enhancements.css` — responsive global mastery and feature layouts.
- `uk11_preview_site/uk11-ux-enhancements.js` — additive presentation screens, six-level dock, unassessed state.
- `uk11_preview_site/UX_AUDIT_20261123.md` — source inspection audit and limitations.

## Desired learner navigation, preserving existing capabilities

Top-level: ScoreMax branding → primary navigation and school/examination selection → **six mastery levels** → student/parent page content.

Student: Home; Schools & Tests; My Study Plan; Practice; Exam Centre; Explore ScoreMax (Weak-area recovery, analytics, Daily Spark, learning capsules, Knowledge Hub, challenges, written practice, teacher/classroom and onboarding destinations).

Parent: Target schools and routes; current level and next action; verified learning progress and coverage; mock outcomes once qualified; study support. Never infer admissions eligibility or prediction.

Teacher: Reuse existing classroom access and workflows after safeguarding/role-based access qualification. Do not fabricate class rosters.

Mobile: accessible navigation and complete six-stage hierarchy immediately below selector; stages may wrap 3×2 on narrow screens; no overflowing fixed horizontal tables; content and next action remain legible.

## Presentation adapter expectations (PROPOSED, not existing API)

No backend endpoint names or database columns are asserted. The following are conceptual view models for mapping to existing APIs; Chat 3 must reconcile field names and contracts rather than adding redundant schemas.

**LearnerContext**
```json
{
  "market": "UK",
  "role": "student",
  "admissions_cycle": null,
  "selected_schools": [],
  "selected_routes": [],
  "subjects": [],
  "verification_state": "unverified"
}
```
Selections must preserve school identity, route, provider and **cycle**. Test membership ≠ eligibility. Deduplicate the *plan* across independently evidenced memberships, not canonical questions across different versions.

**MasteryPresentation**
```json
{
  "current_status": "NOT_YET_ESTABLISHED",
  "next_goal": "FOUNDATION",
  "next_learning_action": "Choose an approved subject/topic diagnostic",
  "eligible_evidence_count": 0,
  "scope": null,
  "as_of": null
}
```
These are conceptual fields, not a database contract. Only qualified independent ScoreMax evidence can drive current stage. Stage labels must be presented **Foundation → Exam Ready → Advanced → Distinction → Expert → Elite**. Foundation–Distinction are topic/chapter; Expert subject-wide; Elite broad/exam-route. Never award on assisted/cosmetic repeat practice.

**FeatureAvailability**
```json
{
  "feature": "study_plan",
  "state": "planned",
  "reason": "Qualified assessment source is not available",
  "available_actions": []
}
```
Use truthful end-user labels such as Available / Demonstration / Planned rather than implying connected functionality from a static illustration.

## Interaction/evidence acceptance

1. New student account displays **Not Yet Established**; school selection leads to relevant subjects without any mark or mastery award.
2. Student selecting multiple official school routes sees one deduplicated subject/topic plan and source/cycle-qualified route applicability.
3. Parent account reads only authorised child context; current mastery/next goal/action mirrors eligible student evidence.
4. Student accesses existing practice, exam centre, Daily Spark, capsules, challenges and recovery from persistent navigation; inactive features are visibly disabled or honestly identified.
5. Exact native response, assessment outcome and eligible evidence are accepted before mastery or analytics updates. No static-demo response updates marks.
6. Teacher role can access only permitted classroom cohorts; no children's data is exposed through demo, analytics or public pages.
7. Mobile viewport acceptance at 320, 375, 390, 768 and 1280 CSS px; keyboard tab/enter/escape; focus after navigation; NVDA/VoiceOver checks; 200% zoom, reduced motion and WCAG contrast audit.
8. Device/browser acceptance must be run against the **deployed commit**; JS syntax and source-regex checks do not prove interactive runtime quality.
9. Do not ship learner-facing internal IDs, academic source keys, rubrics, hidden answers, fabricated scores or admissions probability.

## QA status at handoff

| Item | Status | Evidence |
|---|---|---|
| UK preview isolated branch | PASSED | GitHub branch `preview/uk11-static-site-20261123` |
| Static UK files and paths | PASSED | GitHub fetched three published assets and integration links |
| Render deployment | PASSED (hosting) | `dep-dc28i6mc6qcc73eqebg0` at SHA `1dc6fc3...` reported LIVE |
| Global six-level model and Not Yet Established | PASSED (source inspection) | JavaScript logic and ordered position after route bar |
| Responsive CSS and basic keyboard affordances | PASSED (source inspection) | Breakpoints, focus styles, reduced-motion and skip link |
| Real desktop/mobile browser journeys | PENDING | No authenticated browser device attached; cannot claim tested |
| Accessibility WCAG acceptance | PENDING | Manual/automated audits not yet run |
| Existing Pakistan app module inventory | PENDING | Binary ScoreMax archive not yet inspected |
| Real score/mark/mastery integration | PENDING | Engineering-owned, not present in preview |
| Current-cycle school route governance | PENDING | Academic / authority review required |
| Production / learner release | PENDING | No qualification or authorisation |

## Risk, rollback and immediate engineering next action

**P0:** Never import demo questions into released inventory or allow a demo session to grant achievements. **P1:** Missing real browser/accessibility acceptance, integration inventory, cycle-governed route evidence and authenticated student/parent/teacher state.

**Existing? → Extend? → Reuse? → Simplify? → Build?** Inspect v6.5.12 accepted application source and any later accepted branch before writing UK backend routes. First map the existing student, parent, teacher, study-plan, exam and marking components to this UI. Refuse to duplicate them merely because a static preview has a separate page.

Rollback the static preview to SHA `448b26ee7d40f8a09f0de9dd219d1fe7e612d5ec` if a deployment regression occurs, affecting only the isolated UK preview service. Restore only after verifying service/branch correspondence. This handoff does not authorise a production rollout.
