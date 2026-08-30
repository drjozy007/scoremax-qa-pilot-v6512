# V6.2.8.1 Power House V3 Academic Review Import Contract

## Boundary

This import creates confidential QA review snapshots only. It cannot publish questions, create student attempts, award mastery, alter Study Plans or write into the live ScoreMax question bank.

## Worksheet detection

An Excel worksheet is treated as question-bearing only when a scanned header row contains:

- a supported question header; and
- a supported answer, key or marking-rubric header.

All other sheets are ignored.

## Required content

A row requires:

- Question; and
- either a separate correct answer/key or an explanation/marking rubric capable of acting as the configured answer.

## Source preservation

Every imported reviewer question stores its source worksheet and source row. Confirmed imports are chunked within, not across, source worksheets.

## Governance

`DUAL_REVIEW_REQUIRED` and an affirmative `Reviewer 2 Required` value are immutable routing instructions for the first academic review outcome. An unchanged first-review decision does not bypass the independent second review.

## Confidentiality

Stored import metadata supports audit and routing but is not displayed as wider product architecture to the reviewer. The reviewer interface remains a minimal quiz-style academic judgement surface.
