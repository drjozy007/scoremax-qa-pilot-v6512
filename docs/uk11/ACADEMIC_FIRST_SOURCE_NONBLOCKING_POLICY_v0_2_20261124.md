# UK 11+ — Academic-first QA and non-blocking source metadata
**24 November 2026 | Architecture decision v0.2 | UK-only isolated branch | DESIGN / NOT IMPLEMENTED OR FROZEN**

## Decision (supersedes strict source-evidence language in v0.1)
**Academic correctness, original exam-relevant question quality, and alignment with the governed curriculum/corpus are priority 1.** Do not allow optional bibliographic/source-document metadata, textbook page numbers, worksheet locations, external original-file SHA-256, or lack of a particular school's exam-membership record to become a prerequisite for *authoring or academic QA admission*. A question's **own** immutable version/checksum remains necessary for integrity and is not the same as a third-party book's hash.

This rule addresses the specific FSc Power House bottleneck in which precise source-row provenance became coupled to validation and transfer. The UK adapter must not inherit the FSc/Cross50 requirement for exactly one `question_source_fidelity_v015l1` row, an original master file/row, or blanket `OWNED` assertion for every source. Existing Pakistan production stays untouched.

## Priority and gate matrix

| Scope | Priority | What is required | What must not block |
| --- | --- | --- | --- |
| **Question authoring / academic QA intake** | P0 | Correctness of stem, unique defensible answer, sound independent solution, explicit task/mark demand, age-appropriate subject/topic alignment, curriculum/corpus-backed skill or archetype rationale, honest origin declaration and traceable question content/version | External textbook page/row, external PDF SHA, nonessential bibliographic fields, unresolved exact school/provider/cycle memberships |
| **Academic candidate QA** | P0 | Whole-bank QA checks, distractor quality, unambiguous worked steps, topical exam relevance, independent correction/attack evidence; hold or rectify *genuinely* incorrect/irrelevant questions | Missing optional source documentary metadata; open school route mapping that is not asserted in the learner delivery |
| **School-specific allocation** | Scoped gate | Verified membership for **that school/test/provider/cycle**, without inventing eligibility or format; mapping may be added later | Missing membership for another unrelated school; no need to fork canonical Q |
| **Learner release** | Last-mile safety gate | Quality Wall release approval, correct native rendering/marking, child-safety and privacy checks, sufficient rights to use content, complete question/version integrity; valid route to the chosen learner experience | Optional third-party source page/hash when the question is originally authored and the relevant curriculum/skill is valid |

**Do not confuse syllabus alignment with a copyright source citation.** The approved UK National Curriculum, source register, exam-corpus insight, taxonomy, 135 subskills and 69 archetypes can ground subject/topic relevance. An original question need not correspond to a literal question or row in a published exam paper.

**Provenance must remain honest and cheap.** Store `original_authoring_claim`, `corpus_alignment_basis`, `version_hash`, `rights_declaration`, optional `external_source_reference` / `external_file_hash`, and separate `school_exam_memberships`. Unknown external fields stay missing or pending; never invent opaque IDs, dates, official approvals, hashes or rights.

## Recommended simple UK intake flow
1. Receive one original-authored question and its solution, key/rubric, topic/skill mapping and origin declaration; preserve original bytes/fields and draft lineage.
2. Admit into **PH QA-only staging**, assigning a canonical PH ID/version and checksum. An absent external source document creates a non-blocking metadata task, **not** a `SOURCE_CHECK_REQUIRED` blocking academic defect, unless the stem itself makes a specific source-dependent claim.
3. Run academic checks immediately: maths correctness, solution, difficulty, topic relevance and real test skill; independent checks and whole-bank quality controls. A question that is not academically sound is held for repair.
4. Queue optional enrichment of references, school memberships and source-evidence metadata without delaying independent academic review or authoring of other questions.
5. When academic QA is complete, make candidate content eligible for those learning contexts whose curriculum/topic relevance and delivery format are approved. Bind school-specific memberships only when independently supported for the specific cycle.
6. At final release, guard real rights/child safety/native scorer correctness and exact released-version evidence. Do not allow missing **optional** bibliography to resurrect an intake bottleneck. `ACCEPTED` transfer is not proof of usable question.

## Concrete regression criteria for future code (NOT YET EXECUTED)
- **A: original and academically correct, syllabus-aligned, no textbook row or external SHA** -> QA staging ACCEPT; academic review permitted; no fabricated external proof.
- **B: original and correct, syllabus-aligned, zero school memberships** -> QA staging ACCEPT; can be considered for generic approved study route; school-filtered delivery awaits that school membership.
- **C: wrong mathematical key or indefensible answer, meticulous source references** -> academic HOLD / repair. Bibliography never excuses an academic defect.
- **D: approved real source-derived question with rights restriction** -> QA staging possible; student release HOLD until lawful permission/rights verified.
- **E: one original Q relevant to two distinct school exams** -> one canonical ID/version, two independently evidenced memberships, one independent mastery event per eligible evidence exposure.
- **F: missing topic/skill evidence** -> QA staging for mapping review without invented IDs, no claim of relevance or release until genuine mapping is resolved.
- **G: question content changed after audit** -> new immutable version/updated checksum and requalification; optional external reference changes do not silently change learner content.
- **H: QA-only packet** -> never activates student delivery, mastery, or official exam eligibility.

## Immediate application to UK Maths B01 rectified 40Q
- **40 question drafts stay in academic review scope**; absence of row-by-row original source bytes is **not by itself** a reason to reject original-authoring candidates.
- The 38 READY / 2 SUPPORT status describes *index mapping*, not official school exam eligibility. It does not by itself prove or disprove academic correctness.
- Preserve the 260 **local reference** cases; confirm through exact native scoring before release. Known unit/fraction/currency/thousands-separator risks are functional marking matters and remain P0 for learner release, **not a reason to stop academic authoring/review**.
- Independent Whole-Bank Audit and Gold Recovery remain to be performed; no retroactive PASS, academic clearance, Power House ingestion, paid AI or student-release claims.

## Existing capability and implementation gap
Power House already has QA-only staged transport, effective review projections, content checksums and separate release/mastery fences. The inspected `runtime_support_v015l9g/cross50_qa_staging_contract_v015l9bt.py` is **Cross50-specific** and explicitly requires a source-fidelity row/master SHA; it must NOT be reused unchanged for UK 11+. Extend the existing adaptive semantic mapper and Power House QA-stage envelope for original-authoring claims and optional external-source metadata, while preserving other QC/rights and native scorer protections.

**Untouched:** Pakistan production, PH live DB, frozen contracts, ScoreMax production, UK preview, public learners. This document defines an approved working direction, not a tested implementation or deployment.
