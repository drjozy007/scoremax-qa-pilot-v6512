# ScoreMax V6.2.6 Mastery Laboratory Contract

## Purpose

The Mastery Laboratory proves that ScoreMax can technically receive and reason over a governed candidate corpus without treating it as approved assessment content.

## Admission boundary

An imported candidate must always remain:

```text
QA_SANDBOX_ONLY
NOT_STUDENT_RELEASED
NOT_BANK_APPROVED
NOT_VALID_FOR_REAL_MASTERY
```

Schema validity, Power House origin or an AI review result is never equivalent to ScoreMax bank approval.

## Candidate identity

Every record retains:

- external question ID and version;
- content checksum;
- source lineage;
- programme, subject and chapter;
- concept and LO identities;
- question family and response mode;
- mastery level and mastery ceiling;
- cognitive demand and command verb;
- seed/variant/scaffold/stimulus/recovery relationship;
- answer and marking configuration;
- warnings that remain unresolved.

## Evidence independence

Default technical weights are configurable laboratory values:

| Identity | Default raw weight | Progression use |
|---|---:|---|
| Independent seed | 1.00 | Yes |
| True variant | 0.35 | Capped within seed cluster |
| Scaffold | 0.20 | No independent verification |
| Shared-stimulus pair | 0.50 | Group capped |
| Integrated question | 1.00 | Yes |
| Recovery item | 0.50 | Recovery only |
| Reconfirmation item | 1.00 | Reconfirmation |

A seed cluster or shared-stimulus cluster contributes at most one effective unit per authored mastery level in one phase.

## Scoring boundary

Objective families are scored deterministically from governed marking configuration. Constructed responses require rubric-point or explicit manual sandbox scores. A question requiring manual review receives no automatic full mastery evidence.

## Mastery boundary

Laboratory evidence may produce provisional or synthetic verified states for technical testing. It never creates or updates a real `mastery_records` row.

A decision must preserve:

- metrics used;
- threshold checks;
- relationship caps;
- state before and after;
- reason for the decision;
- recovery need;
- next Study Plan action that would be recommended if this were valid evidence.

## Promotion boundary

There is no V6.2.6 laboratory-to-live promotion route. Candidate promotion remains a separate future Content Admission process requiring academic approval and release governance.
