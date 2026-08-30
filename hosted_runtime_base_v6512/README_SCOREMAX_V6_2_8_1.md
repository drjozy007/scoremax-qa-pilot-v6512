# ScoreMax V6.2.8.1 — Power House V3 Reviewer Import Compatibility

V6.2.8.1 supersedes V6.2.8 as the controlled-pilot baseline.

## Purpose

This is a focused compatibility and governance patch for the real Power House Chapter 1 academic-review workbook:

`PH_CH1_Final_Academic_Review_Workbook_Post_AI_Assurance_v3_0.xlsx`

The V6.2.8 importer incorrectly opened only the active instructional sheet and did not recognise the workbook's governed review headers. V6.2.8.1 detects every question-bearing worksheet, ignores instructional/reference tabs, maps the Power House fields automatically and creates review batches without mixing source sheets.

## Power House V3 workbook behaviour

ScoreMax now automatically recognises:

- `Batch 1 Review`
- `Batch 2 Review`
- `Batch 3 Review`

It ignores sheets that do not contain both a supported question field and an answer/rubric field, including the workbook's instructional and reference tabs.

Automatic mappings include:

- `Question / Task` → Question
- `Stimulus / Context` → Context
- `Statements / Options` → reviewer content and option choices
- `Key Answer` → Configured answer
- `Explanation / Marking Rubric` → Explanation/rubric
- `Question ID` → External question ID
- `Question Type` → Question type
- `Mastery` → Proposed mastery
- `Priority` → Review priority
- `Review Requirement` → Review governance
- `Reviewer 2 Required` → pre-governed second-review requirement

A rubric-based constructed response may be imported when `Key Answer` is blank but `Explanation / Marking Rubric` contains the configured marking answer.

## Batching

The three source sheets remain separate. ScoreMax creates batches of at most 100 within each source sheet, so no batch crosses from one original workbook sheet into another.

The governed acceptance fixture contains:

- Batch 1 Review: 1,199 records → 12 ScoreMax batches
- Batch 2 Review: 1,168 records → 12 ScoreMax batches
- Batch 3 Review: 1,199 records → 12 ScoreMax batches
- Total: 3,566 records → 36 ScoreMax batches

## Reviewer view

The reviewer still sees only the confidential review material required for judgement:

- chapter/topic;
- question;
- stimulus/context where supplied;
- statements, matching content or options;
- configured answer/rubric;
- explanation;
- proposed mastery level;
- mastery suitability;
- decision and comments.

No wider ScoreMax or Power House architecture is exposed.

## Dual-review governance

Imported `DUAL_REVIEW_REQUIRED` or `Reviewer 2 Required = YES` items remain second-review-required even when Reviewer 1 selects `Accept unchanged`. Other items continue to require a second review whenever Reviewer 1 changes, rejects, reclassifies or is unsure about the question.

## Start locally

On Windows:

```text
start_scoremax_v6_2_8_1.bat
```

Or:

```bash
python app.py
```

On first launch, use the bootstrap Admin credentials printed in the terminal. The login field accepts email, formal ScoreMax User ID or username.

## Upgrade

Install V6.2.8.1 separately and test it against a copied V6.2.8 database. Do not overwrite the only working installation or migrate the only valuable database. See `V6_2_8_1_MIGRATION_GUIDE.md`.
