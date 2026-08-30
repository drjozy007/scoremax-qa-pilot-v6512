# V6.2.8 Guided Reviewer Import Contract

## Purpose

Allow Admin to import a large governed question-bank file without first converting it to a hidden exact schema, while preserving the confidential, QA-only Academic Reviewer Workspace.

## Import boundary

- accepted formats: JSON, CSV and XLSX;
- maximum rows per import: 10,000;
- batch size after confirmation: maximum 100;
- required semantic fields: Question and Correct answer;
- optional fields: Question ID, chapter, topic, options, explanation, mastery level and calibration decision;
- common column headings are suggested automatically;
- Admin confirms the mapping before records are created;
- invalid rows are retained in an error report instead of aborting valid rows;
- confirmation is atomic: either every valid generated batch is created or none is committed.

## Confidentiality

Only the minimal reviewer snapshot is written to the reviewer tables. The import engine does not copy internal concept/LO ledgers, source lineage, question-family architecture, Study Plan rules or live-bank control metadata.

## Assignment groups

Admin can assign one or multiple batches to one reviewer. Only the first batch issues the secure invitation; accepting it activates the other pending batches in the same assignment group. Progress, decisions, timing and quality evidence remain independently auditable per batch.

## Reviewer choice

Completing a batch presents a clear choice to stop or continue to the next assigned batch. No reviewer is required to complete every assigned batch in one session.

## Publication boundary

Guided imports and academic review decisions do not publish, activate or modify live ScoreMax questions. Content Admission remains a separate future governed step.
