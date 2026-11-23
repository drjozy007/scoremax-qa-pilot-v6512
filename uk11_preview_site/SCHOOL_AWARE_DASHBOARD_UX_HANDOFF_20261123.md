# ScoreMax UK 11+ — School-aware post-sign-in UX implementation

Date: 23 November 2026
Owner: Product & UX
Branch: `preview/uk11-static-site-20261123`
Lifecycle: static UK preview IMPLEMENTED; authentication, persistence and runtime acceptance PENDING.

## Requirement

After an authenticated learner chooses one or more schools, ScoreMax must derive its visible learning layout using evidence-backed **School → admission route → provider/test → entry cycle → subject/skill** relationships. If a test is shared, show one test card and one combined subject group. Never display unrelated exam subjects as though they are required.

**The existing preview has no login.** This implementation demonstrates the student home that would appear **after sign-in**. Login, student-account persistence, authorisation and server enforcement are Chat 3 integration tasks, not claims of this implementation.

## Implemented on isolated preview

- `uk11_context_dashboard.js`: school-aware student home, subject cards, test cards, contextual navigation, parent dashboard, practice and mock views, route summary directly above persistent six-level dock, and front-end guards on out-of-scope practice/mocks.
- `uk11_context_dashboard.css`: scoped responsive styles; two-column subject/test layouts wrap to single-column on mobile.
- `index.html`: additive assets loaded after the existing school catalogue, without modifying the subject/question bank.

The selected-school context is derived on each render; switching schools updates displayed subjects, test routes, links and headings. No eligible mapping generates a verified no-subject state instead of showing all four general subjects.

## School routing and presentation rules

1. **Zero selected schools:** existing general preview remains available (no invented personalised login).
2. **One mapped school:** show its mapped test route and linked subject(s), avoiding unrelated subject cards.
3. **Multiple mapped schools:** show the union of relevant subjects; shared tests appear once.
4. **Previous-cycle official reference:** show matched routes and subjects provisionally with prominent warning to confirm the 2028 intake.
5. **School lacking sufficient mapping:** still selectable; no invented test or subject. Display explicit confirmation/pending state.
6. **Mixed verified/historical/unmapped:** show the subjects derived from mapped schools only, plus warnings for unmapped choices.
7. **Alternative test pathway (OR):** school-catalogue evidence must not be converted into a requirement to sit both exams. Full alternative sequencing remains engineering/policy-gated.
8. **School choice changes while previewing a question:** discard an out-of-scope in-session quiz when returning to the contextual layout. This UI safeguard does not replace server entitlement checks.
9. **Mastery:** six levels remain in the global masthead below exam selection; new students stay **Not Yet Established**, regardless of subject or school.
10. **Broader ScoreMax:** study plans, recovery, Daily Spark, capsules, Knowledge Hub, challenges, written tasks and the parent view remain accessible. They are explicitly unmarked/static where not connected.

## Illustrative acceptance cases (source-code simulation)

| Scenario | Expected result | Result |
|---|---|---|
| No school selected | General preview retained | PASSED |
| Two Bucks schools | One Bucks test, three mapped subjects; English absent | PASSED |
| Two Bucks + one Slough school | Two distinct tests, four relevant subjects | PASSED |
| One unmapped school | No fabricated subject or test | PASSED |
| One mapped + one unmapped school | Mapped subjects only, plus pending warning | PASSED |
| Parent with Bucks + Slough | Family view reflects four mapped subjects; no invented results | PASSED |
| JS syntax and HTML asset loading | No syntax errors, assets linked | PASSED (static inspection) |
| Real desktop/mobile/browser flow | Check actual deployed UI and accessibility | PENDING |
| Authenticated post-login route restoration | Rehydrate saved learner choices from existing server | PENDING |
| Native marking, actual study-plan eligibility, mastery | Qualify exact existing ScoreMax engine | PENDING |

## Chat 3 binding contract (conceptual; NOT approved API or DB schema)

The authenticated ScoreMax service should provide, per child and admissions cycle:
- Selected school **official identifiers** (not name-only string matching);
- Verified school route memberships and effective dates, with separate test/provider IDs;
- Required **AND**, optional **OR**, conditional and sequential exam branches;
- Provider-specific subjects/skills/formats, labelled provenance and change/withdrawal information;
- Entitled role access for student, linked parent and teacher;
- Mastery status, next goal, independent eligible evidence, recommended learning actions.

**Server-side** authorisation must restrict exam allocation, search, item delivery, marking and mastery updates to eligible routes. Hiding a client-side navigation tile is not security.

Any change in admissions cycle, school, test provider or membership must invalidate/regenerate the scoped study plan safely, preserving assessment history and avoiding corrupt or orphaned mastery claims.

## Status and untouched boundaries

PASSED: static implementation, syntax, route/subject layout simulations and source references.
PENDING: real mobile/browser and screen-reader acceptance; authenticated runtime; full official school mapping/cycle checks; integrated ScoreMax capability inventory.
N/A: academic question release approval, ingestion, or native scorer changes from this UX chat.

Untouched: Pakistan deployment, frozen contracts, Power House academic records, production data/migrations, credentials and existing ScoreMax native-marking logic.

Rollback: restore prior isolated UK preview commit `83b1ecd6a104fa554cded5876e3a66078601fbdf` and redeploy UK preview only if a verified regression occurs.
