# ScoreMax V6.2.2 Independent Review Brief

## Review focus

1. Reproduce the old journey on V6.2.1: choose Biology and observe the all-subject template being reused.
2. Verify V6.2.2 renders `subject_detail.html` and passes only the Biology object.
3. Test Biology, Chemistry and Physics through genuine browser requests.
4. Confirm no subject can fall through to another subject's chapter section.
5. Inspect the student desktop header for duplicate links and confirm the six top-level journeys.
6. Test mobile More-menu opening and the simplified bottom bar.
7. Re-run the V6.2.1 live session test to ensure this UX patch does not regress authentication.

## Expected result

- `/student/subjects` shows all subject choices.
- `/student/subject/Biology` shows Biology only.
- `/student/subject/Chemistry` shows Chemistry only.
- No database migration is required.
- All 186 automated checks pass.
