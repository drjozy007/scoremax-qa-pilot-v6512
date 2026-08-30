# ScoreMax V6.2.5 — Sustainability, Public Trust & Daily Spark

V6.2.5 extends the verified V6.2.4 curriculum-isolation and accessibility baseline with two governed product capabilities:

1. **Sustainability & Public Trust** — a public ScoreMax section that separates current practice, work in progress and future commitments, backed by policies, owners, evidence boundaries, targets and progress reports.
2. **Daily Spark MVP** — one compact student-dashboard module containing a personalised Academic Spark and an age-appropriate English Word of the Day.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Or use `start_scoremax_v6_2_5.bat` on Windows.

## Important boundaries

- Academic Sparks transform existing approved ScoreMax questions; they do not create a second academic bank.
- Demo content is not served to real student accounts through Academic Spark.
- Daily Spark responses are engagement/diagnostic evidence only and cannot award formal mastery.
- Word of the Day is selected from a stored controlled library; no live AI call is required per student or per day.
- Growth Engine sustainability drafts enter `DRAFT_REVIEW_REQUIRED` and cannot publish themselves.
- Public sustainability claims must remain labelled as `CURRENT_PRACTICE`, `IN_PROGRESS` or `FUTURE_COMMITMENT`.

See `V6_2_5_BUILD_REPORT.md`, `V6_2_5_ACCEPTANCE_CHECKLIST.md` and `V6_2_5_MIGRATION_GUIDE.md`.
