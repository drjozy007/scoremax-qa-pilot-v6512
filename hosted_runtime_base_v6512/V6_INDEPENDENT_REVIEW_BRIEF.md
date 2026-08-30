# Independent Review Brief — ScoreMax V6.0

Review the actual source and execute the supplied tests. Do not infer implementation from this brief alone.

## Priority questions

1. Can any unapproved or tampered Power House package become active?
2. Are package, question, rubric and policy versions pinned immutably to every attempt and mark?
3. Can improvement or OCR correction overwrite original assessment evidence?
4. Can the written marker directly award/overwrite ScoreMax mastery rather than producing evidence?
5. Can provisional/uncertain marking count as strong mastery evidence?
6. Can an exemplar be published without a perfect confirmed independent score, academic approval and separate opt-in consent?
7. Does hiding the exemplar feature remove public access without deleting evidence?
8. Are student-uploaded pages private and production storage fenced?
9. Are Mock Mode restrictions enforceable server-side?
10. Are feature/access/date controls applied server-side, not only in templates?
11. Are external provider claims honest and are local simulations clearly labelled?
12. Does V6 preserve all V5.5 blueprint/calibration behaviour?

## Execute

```bash
python smoke_tests_v6.py
python smoke_tests_v5_5.py
```

Then complete browser acceptance using `V6_ACCEPTANCE_CHECKLIST.md`.

## Known boundaries

- no production OCR provider is bundled;
- no validated high-stakes AI marking claim is made;
- exemplar library is HIDDEN by default;
- academic and privacy validation remain pre-live requirements.
