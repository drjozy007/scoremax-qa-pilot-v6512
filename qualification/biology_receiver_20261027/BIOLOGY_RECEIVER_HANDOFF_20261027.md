# ScoreMax Biology receiver readiness — 27 October 2026

RECEIVER READY: NO for the live service until the qualified receiver overlay is promoted and its live checks pass. The engineering candidate is ready for that promotion. Academic population and the first actual Biology delivery are separate pending steps.

## Accepted baseline and exact candidate
- Accepted public source: 9df838d46ad82633904f252108ba434be90f9bb3; current live deploy dep-dbfn4tgn74is73f17p2g.
- Qualified engineering commit: 1b21042012af0b1aefce79c4cc86f2182d4f6b75, branch fix/scoremax-streamed-backup-20261022.
- Runtime: 261 files; SHA-256 ddb4ee4a1398c0e5ac2300e4711b7a1befadd7e4ef067dfc21bc28de118cdc9c.
- Build command: python -B scripts/materialize_scoremax_biology_receiver_20261027.py && pip install -r scoremax_runtime_v669b/requirements.txt
- The build verifies the frozen public runtime and applies only five reviewable source deltas. AI candidate code is not applied.
- Render service srv-daj5fbm7bikc73aq2gdg, existing Standard plan, one instance, 5 GB disk. No compute, disk, secret, start-command, access or exposure change is proposed.
- Auto-deploy is off. The attempted build-setting save returned Unauthorized and was cancelled; no deploy was triggered. Render browser reauthentication is pending.

## ALREADY SUPPORTED
Reuse the native signed receiver, strict envelope/manifest/member checksums, exact idempotency keys and durable delivery receipts, immutable question-version store, separate release memberships, explicit product authorisations, staging, activation, withdrawal, native scoring contracts, governed guided self-assessment, assessment answer pins, persistence, results, access and mastery safeguards. Bulk membership/version receiving already uses a transaction per package, rather than a transaction per question. No new importer, database, staging system, dashboard or marking engine was introduced.

## ACTUAL GAPS FIXED
1. Opaque source chapter IDs and repeated batch memberships could produce incorrect catalogue matches/counts. The catalogue now uses actual native placements and source chapter number/name, deduplicates canonical question IDs, and appends governed chapters missing from placeholder navigation without inventing labels.
2. Question format and section choices were absent; type and topic scopes could be applied too late or across chapters. Native canonical type and exact source section filtering now run before sampling. Topic links retain their parent chapter. Actual counts, section links and unavailable content are shown through existing views.
3. MDCAT examination/mock selection now filters MCQ-only before sampling and centrally rejects incompatible sessions. Broad supported practice content remains available through its approved memberships. Structured practice and guided unscored restrictions remain in place.
4. A saved assessment could resume after its release was superseded but fail at submission. The submission path can now use its already validated immutable native answer pin and original authorised SUPERSEDED placement. Withdrawn, staged, quarantined, academically inactive and excluded content do not gain this fallback.
5. Release withdrawal/replacement could hide a shared question still eligible under another active authorised release. Only rows active immediately before that release operation may retain another exact active membership. Earlier academic question withdrawal remains effective.
6. Exact accepted replay no longer redownloads/recompiles the same verified package. Strict request schema/checksum checks still run first and native durable replay/ACK accounting remains.
7. Manifest HTTP reads and ZIP expansion are bounded by the existing upload byte cap before expansion, while original signing, host, traversal, member and checksum protections remain.
8. Four additive lookup indexes address demonstrated reverse-membership/identity/answer lookups. They are created after existing schema reconciliation. No destructive migration or table/column replacement is included.

Changed runtime files: app.py; scoremax_integration_v1.py; ux_catalogue_browser.py; templates/test_setup.html; templates/chapter_page.html. Native grading, mastery, access, withdrawal bridge and persistent storage guard modules are byte-identical to the accepted public runtime. Existing app access/mastery/teacher functions outside the named receiver/student-scope changes are AST-identical.

## BIOLOGY ROUTING
FSc Part I and Part II use each governed question's exact native programme/year, chapter, section and topic metadata. MDCAT uses only explicit accepted crosswalk/release memberships. A question shared between programmes retains one canonical content identity/version with separate placements. No chapter codes, crosswalks, missing questions, academic approvals or scoring authority were generated.

All existing supported native formats use the established canonical type/contract interpreter. Guided self-assessment remains explicitly unscored; unsupported scoring contracts remain held/rejected. An unsupported question rejects its atomic governed package with question/version/error evidence; there is no silent partial admission. Power House must deliver independently governed supported batches, or already governed guided contracts, so one unsupported atomic package does not prevent separate valid packages from proceeding. ScoreMax does not rewrite source contracts or weaken admission.

## VOLUME READINESS
The architecture supports repeated governed batches and deeper chapter inventories, including chapters containing 300 or 1,500 questions, within actual package-byte and storage admission limits. This is compatibility readiness, not a measured production capacity certificate for an arbitrary 1,500-question payload or the whole syllabus.
- Existing default upload cap is 40 MiB (SCOREMAX_MAX_UPLOAD_MB), now enforced for downloaded raw archives and total expanded ZIP member bytes. Existing production configured cap must be respected.
- Replays of the same exact accepted package are idempotent. Changed content under the same release identity/version/checksum is not accepted.
- PUBLISH_SNAPSHOT is a complete snapshot for its release identity. Subsequent versions replace that release's snapshot; they are not append chunks. Use existing distinct governed batch release IDs or complete replacement snapshots with the native product authorisation. The catalogue aggregates distinct question IDs across valid batch memberships.
- Existing student session selection remains bounded at 100 questions; chapter inventory size does not become one unbounded student assessment.
- No per-question extrapolation from earlier capacity results. Reused 393-question inactive staging evidence measured DB growth 10,072,064 bytes (including 192,512 index bytes), filesystem growth 11,976,704 bytes and retained two-copy demand 206,311,424 bytes, in its exact isolated scope. It does not certify the entire live database layout or future content volume.
- Existing disk reserve, admission and startup guard remain fail-closed. No reserve reduction, cost increase or unlimited import claim.
- Reuse the previously accepted separate-app controlled workload/recovery evidence; do not rerun Cross50, historical ACKs/transfers, fictional 300/1,500 banks or general Gate D qualifications.

## STUDENT EXPERIENCE
Focused native HTTP/Jinja tests cover chapter navigation/counts/sections, type selection before sampling, chapter-isolated topics, broad MDCAT practice/MCQ-only mocks, guided-only navigation and unscored submission, exact historical saved-session resume/submission/result, and withdrawn-content denial. Accepted responsive styles and prior physical-phone login/practice/question evidence are retained.
The new controls have not been visually verified in a desktop browser or on a physical phone. The disposable localhost preview could not be loaded; a subsequent file preview was blocked by the browser URL policy. No policy bypass or substitute claim of visual verification was made. Native server-side tests passed. The first actual chapter journey must include desktop and mobile verification.

## DEPLOYMENT, TESTS AND ROLLBACK
[Focused Linux run](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/40488611459) passed at exact candidate 1b21042012af0b1aefce79c4cc86f2182d4f6b75:
- 15 accepted-baseline reproduction/affected cases and 15 candidate native receiver/student cases.
- Four manifest boundary cases and the affected existing signed-download security qualification.
- Actual cold rollback: accepted public code booted through the unchanged native guard against a disposable database written by the candidate, kept four additive indexes, resumed its saved answer, submitted for 100% native score, and displayed the final result. No database restore.
- 10.537125053 seconds total; memory peak 165,801,984 bytes; all new memory.events counters zero. CPU quota throttling was recorded: 13 periods, 5,735 microseconds (0.005735 seconds). No historical owner exception is applied to this run.
- Container: existing CI, 2 GiB memory, 1 CPU, 1 GiB temporary data mount, network disabled. Synthetic protocol fixtures only; no academic bank approval, production database, historical transfer or AI call.
- Artifact 12726635799; ZIP SHA-256 a4e837ba087e7f7d6652f3b33462101617a7201b5e71589c21d8aca1b037d048; retained 14 days. Source compatibility and condensed receipts are preserved beside this handoff.
Earlier failed jobs remain failed: fixture provenance/access errors and one real fresh-schema index-order defect were corrected before this final success. No failed memory result was relabelled.

Promotion procedure: confirm branch head and exact build materializer; save the Biology-only build command; keep auto-deploy off; trigger one exact qualified revision; monitor the resulting deploy through live; verify runtime fingerprint, unchanged native startup/guard and database health, ordinary public responses and authorised student scopes. Do not import or activate content as part of this code promotion.

Rollback target: retained public deploy dep-dbfn4tgn74is73f17p2g / commit 9df838d46ad82633904f252108ba434be90f9bb3. Roll back application code using the retained build; do not restore an old database over subsequent student work. If rebuilding instead, restore the accepted public build command. Retain the additive indexes. Verify deploy status, unchanged guard, normal student session and result access; keep auto-deploy off. A disk-backed service has a deployment interruption, and code rollback does not roll back its disk.

## First actual chapter, then reuse
No new governed Biology package was delivered during this task. When one arrives:
1. Record exact signed package/release identity/version, approved chapter/programme placements, native marking/guided eligibility, bytes and lineage without editing content or authorisation.
2. Run existing capacity admission against the actual archive/database/WAL/backup reserve; record actual storage growth and operational margin. Stop at an exact failed admission; do not increase costs or relax reserves.
3. Receive once through the established signed channel, inspect the native durable ACK and immutable source/version/hash counts, and apply only the separately authorised native product activation. Do not replay earlier transfers.
4. Reconcile distinct canonical counts and FSc I/II/MDCAT placements, held/unavailable labels, chapter/section/topic/types; confirm unsupported packages remain isolated and exam/mock eligibility is MCQ-only.
5. Use an existing authorised tester to practise and repeat, save/resume, submit and view native feedback/results/progress on desktop and mobile. Check that earlier saved attempts/results remain intact.
6. Preserve this actual chapter receipt, then reuse the same bounded path for subsequent chapters; investigate only a changed contract, failed capacity check or new demonstrated defect.

Power House academic governance/release authority remains with the owner. No Power House operations or engineering occurred, no real question imports/activations occurred, no new hosting was purchased, and the paid AI candidate remains separate with budget zero.
